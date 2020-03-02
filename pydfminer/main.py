from pprint import pprint
import json
import pdb
import traceback
import re
import logging

from treelib import Node, Tree
from transitions import Machine, State
from transitions.extensions.states import add_state_features, Volatile

import fire
import tabula

logging.basicConfig(level=logging.DEBUG)
# Set transitions' log level to INFO; DEBUG messages will be omitted
logging.getLogger('transitions').setLevel(logging.DEBUG)

log = logging.getLogger(__name__)
log.setLevel(level='DEBUG')

# institution classifier
## bank
# - page
# - statement period
# - entitity
# - accounts
# - fees
# - deposits
# - withdrawls

### becu [pdf parse]
## financial services
### square [connect to api?]
### stripe
### paypal



# Volatile -- initialises an object every time a state is entered

#     keyword: volatile (class, optional) -- every time the state is entered an object of type class will be assigned to the model. The attribute name is defined by hook. If omitted, an empty VolatileObject will be created instead
#     keyword: hook (string, default='scope') -- The model's attribute name fore the temporal object.
@add_state_features(Volatile)
class CustomStateMachine(Machine):
    pass


class Document(Tree):
    def __init__(self, document):
        super().__init__()
        self.document = document
        self.machine = CustomStateMachine(auto_transitions=False)
        self.machine.add_model(self)

    def page(self):
        pass

    def row(self):
        pass

    def col(self):
        pass

    def run(self):
        previous_state = None

        try:
            while self.state != 'terminus' and previous_state != self.state:
                triggers = self.machine.get_triggers(self.state)
                log.debug(f"run:st {self.state} tr {triggers}")
                for trigger in triggers:
                    if self.trigger(trigger, self.row()):
                        break
                log.debug(f"run:st {self.state} tr {trigger} worked")
            log.debug(f"run:complete state {self.state} prev {previous_state} row {self.row()}")
        except IndexError:
            log.debug(f"run:complete out of document, state {self.state} prev {previous_state}")



class PdfDocument(Document):
    def __init__(self, document):
        super().__init__(document)
        self.location = {
            'page': 0,
            'row': 0,
            'col': 0
            }

    def page(self):
        return self.document[self.location['page']]['data']

    def row(self):
        return self.page()[self.location['row']]

    def col(self):
        return self.row()[self.location['col']]

    def consume_row(self):
        r = self.row()
        self.location['row'] = self.location['row'] + 1
        return r


class Becu(PdfDocument):
    def __init__(self, document):
        super().__init__(document)

        self.bank = Bank(tag="BECU", data=self)
        self.add_node(self.bank)

        initial = self.section_initial()
        section_transitions = []
        last = self.section_summary(
            [initial],
            regex="Summary of Deposit",
            tag="summary_deposit_account"
            )
        section_transitions.append(last)

        last = self.section_summary(
            section_transitions,
            regex="Summary of Loan",
            tag="summary_loan_account",
            fee_section=False
            )
        section_transitions.append(last)

        last = self.section_detail(
            section_transitions,
            regex="Deposit Account",
            tag="deposit_account"
            )
        section_transitions.append(last)

        last = self.section_detail(
            section_transitions,
            regex="Loan Account",
            tag="loan_account"
            )
        section_transitions.append(last)

        # todo: add page breaks [use nested states, so page break can return to
        # same place in Section when resumed
        #
        # contues to sections

    def section_initial(self):
        section = Section(tag="initial", data=self)
        self.add_node(section, parent=self.bank)

        contents = [Address(data=self), StatementPeriod(data=self)]
        for item in contents:
            self.add_node(item, parent=section)

        self.machine.initial = section

        linear_transitions = [section, *contents]

        for from_, to_ in zip(linear_transitions, linear_transitions[1:]):
            self.machine.add_transition("from_" + from_.tag, from_, to_,
                                        conditions=[from_.done,
                                                    to_.ready]
                                        )

        last = contents[-1]

        return last

    def page_boundary(self):
        pass

    def add_incomming_transitions(self, incomming, target):
        for last in incomming:
            self.machine.add_transition(
                last.tag, last, target,
                conditions=[last.done,
                            target.ready])

    def add_outgoing_transitions(self, tag, from_, outgoing):
        for target in outgoing:
            self.machine.add_transition(
                f"{tag}:{from_.tag}_TO_{target.tag}", from_, target,
                conditions=[from_.done,
                            target.ready])

    def section_summary(self, incomming, regex, tag, fee_section=True):
        summary = OptionalSection(section_regex=regex, tag=tag, data=self)
        self.add_node(summary, parent=self.bank)

        self.add_incomming_transitions(incomming, summary)

        node = self.add_node(BlockHeader(tag="BlockHeader/Acc", lines=2, data=self),
                             parent=summary)
        self.machine.add_transition(summary.tag, summary, node)

        last = self.add_node(
            AccountsSummaryLine(
                section_regex="checking|savings",
                data=self),
            parent=summary)
        self.machine.add_transition(node.tag, node, last)
        self.machine.add_transition("self_" + last.tag, last, last,
                                    conditions=[last.ready])

        if fee_section:
            node = self.add_node(BlockHeader(tag="BlockHeader/Fee", lines=1, data=self), parent=summary)
            self.machine.add_transition(last.tag, last, node)
            last = self.add_node(
                FeesSummary(
                    section_regex="fees",
                    data=self),
                parent=summary)
            self.machine.add_transition(node.tag, node, last)
            self.machine.add_transition("self_" + last.tag, last, last,
                                        conditions=[last.ready])
        return last

    def section_detail(self, incomming, regex, tag):
        detail = OptionalSection(section_regex=regex, tag=tag, data=self)
        self.add_node(detail, parent=self.bank)

        self.add_incomming_transitions(incomming, detail)

        account = self.add_node(
            AccountDetailHeader(
                section_regex="checking|savings",
                data=self),
            parent=detail)
        self.machine.add_transition(f"{tag}:{detail.tag}", detail, account)

        yield_ = self.add_node(
            AccountDetailYield(
                data=self,
                section_regex="yield"),
            parent=account)
        self.machine.add_transition(f"{tag}:{account.tag}", account, yield_)

        header = self.add_node(
            AccountActivityHeader(
                section_regex="desposits|withdrawals|checks",
                data=self),
            parent=account)
        self.machine.add_transition(f"{tag}:{yield_.tag}_TO_{header.tag}",
                                    yield_, header)
        # if there is no yield section
        self.machine.add_transition(f"{tag}:{account.tag}_TO_{header.tag}",
                                    account, header)

        line = self.add_node(
            AccountActivityLine(
                section_regex="[0-9]{2}/[0-9]{2}",
                data=self),
            parent=header)
        self.machine.add_transition(f"{tag}:{header.tag}", header, line)
        self.machine.add_transition("self_" + line.tag, line, line)
        self.add_outgoing_transitions(tag, line, [account, header])

        return line

    def add_node(self, node, parent=None):
        super().add_node(node, parent=parent)
        self.machine.add_state(node)
        return node


class NodeState(State, Node):
    def __init__(self, *args, **kwargs):
        if 'tag' not in kwargs:
            kwargs['tag'] = self.__class__.__name__
        name = kwargs.get('name', kwargs['tag'])
        # node consumes data
        Node.__init__(self, *args, **kwargs)
        State.__init__(
            self,
            name,
            on_enter=kwargs.get('on_enter'),
            on_exit=kwargs.get('on_exit'),
            ignore_invalid_triggers=kwargs.get('ignore_invalid_triggers')
            )

    def enter(self, event_data):
        """ Call on_enter method on state object """
        log.debug("%s.enter '%s' callback.", self.__class__.__name__, self.tag)
        if hasattr(self, 'on_enter_state') and callable(self.on_enter_state):
            self.on_enter_state(event_data)
        State.enter(self, event_data)

    def exit(self, event_data):
        """ Call on_exit method on state object """
        log.debug("%s.exit '%s' callback.", self.__class__.__name__, self.tag)
        if hasattr(self, 'on_exit_state') and callable(self.on_exit_state):
            self.on_exit_state(event_data)
        State.exit(self, event_data)

class TerminalState(NodeState):
    def __init__(self, *args, **kwargs):
        kwargs['tag'] = 'terminus'
        super().__init__(*args, **kwargs)

class Bank(NodeState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Section(NodeState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def ready(self, row):
        log.debug(f"{self.__class__.__name__}[{self.name}] is ready")
        return True

    def done(self, event_data):
        log.debug(f"{self.__class__.__name__}[{self.name}] is done")
        return True

class RegexMatchingSection(Section):
    def __init__(self, *args, section_regex, **kwargs):
        super().__init__(*args, **kwargs)
        self.regex = re.compile(section_regex, flags=re.IGNORECASE)

    def ready(self, row):
        search = None
        for col in row:
            search = self.regex.search(col['text'])
            if search:
                break
        log.debug(f"{self.__class__.__name__}[{self.name}] ready:{search} {self.regex.pattern}")
        return search != None

class OptionalSection(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())

class Address(Section):
    def __init__(self, *args, **kwargs):
        log.debug(f"{self.__class__.__name__} {args} {kwargs}")
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())
        print(self.data.consume_row())
        print(self.data.consume_row())

class StatementPeriod(Section):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())

class BlockHeader(Section):
    def __init__(self, *args, lines=1, **kwargs):
        self.lines = lines
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        for _ in range(self.lines):
            print(self.data.consume_row())


class AccountsSummaryLine(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())

class FeesSummary(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())

class AccountDetailHeader(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())

class AccountDetailYield(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())
        print(self.data.consume_row())
        print(self.data.consume_row())

class AccountActivityHeader(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())
        print(self.data.consume_row())

class AccountActivityLine(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        print(self.data.consume_row())




def process(pdf='/Volumes/2019 Google Drive/Google Drive/foolscap/archive/Financial Accounts/BECU/2020/becu  2020-01-01 2020-01-31 littlecatz Estatement.pdf'):
    pdf_json = tabula.read_pdf(pdf, pages='all', output_format='json', multiple_tables=True, relative_area=True, area=[0,0,100,100], lattice=False, stream=True)
    #print(json.dumps(pdf_json, indent=2))

    doc = Becu(pdf_json)
    log.debug(doc.machine.states.keys())
    log.debug(doc.machine.get_transitions())
    doc.show(line_type="ascii-em", reverse=False, idhidden=False, key=False)
    doc.run()
    #pprint(doc.state)
    #doc.show(line_type="ascii-em", reverse=False, idhidden=False, key=False)


if __name__ == '__main__':
    try:
        fire.Fire()
    except:
        traceback.print_exc()
        pdb.post_mortem()
