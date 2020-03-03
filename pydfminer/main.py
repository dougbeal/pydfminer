from pprint import pprint
import json
import logging
import pdb
import re
import traceback

from treelib import Node, Tree
from transitions import Machine
#from transitions import HierarchicalMachine as Machine
from transitions import State
#from transitions import NestedState
from transitions.extensions.states import add_state_features, Volatile

import fire
import tabula

#NestedState.separator = '↦'

logging.basicConfig(level=logging.INFO)
# Set transitions' log level to INFO; DEBUG messages will be omitted
logging.getLogger('transitions').setLevel(logging.INFO)

log = logging.getLogger(__name__)
#log.setLevel(level=logging.INFO)
log.setLevel(level=logging.DEBUG)

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
        # used for returning to previous state when page ends
        self.previous_state = None

    def page(self):
        pass

    def row(self):
        pass

    def col(self):
        pass

    def run(self):
        try:
            # stop if there is no where to go
            triggers = True
            successful_trigger = True
            while self.state != 'terminus' and triggers and successful_trigger:
                self.previous_state = self.state
                triggers = self.machine.get_triggers(self.state)
                log.debug(f"run:st {self.state} tr {triggers}")
                for trigger in triggers:
                    successful_trigger = self.trigger(trigger, self.row())
                    if successful_trigger:
                        break
                log.debug(f"run:st {self.state} tr {trigger} worked")
            log.debug(f"run:complete state {self.state} prev {self.previous_state} row {self.row()} suc {successful_trigger}")
        except IndexError:
            log.debug(f"run:complete out of document, state {self.state} prev {self.previous_state}")



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

    def consume_page(self):
        self.location['col'] = 0
        self.location['row'] = 0
        self.location['page'] = self.location['page'] + 1



class Becu(PdfDocument):
    def __init__(self, document):
        super().__init__(document)

        self.bank = Bank(tag="BECU", data=self)
        self.add_node(self.bank)

        self.page_boundary = PageBoundary(
            section_regex="page [0-9]+ of [0-9]+",
            data=self)
        self.machine.add_state(self.page_boundary)

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

        self.add_outgoing_transitions(
            'pagebreak',
            self.page_boundary,
            section_transitions)

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
        # continued

        line = self.add_node(
            AccountActivityLine(
                section_regex="[0-9]{2}/[0-9]{2}",
                data=self),
            parent=header)
        self.machine.add_transition(f"{tag}:{header.tag}", header, line)
        self.machine.add_transition("self_" + line.tag, line, line)
        self.add_outgoing_transitions(tag, line, [account, header])

        return detail

    def add_node(self, node, parent=None):
        super().add_node(node, parent=parent)
        self.machine.add_state(node)
        if hasattr(node, 'ready'):
            self.machine.add_transition(
                "from_" + node.tag + "_to_pagebreak",
                node,
                self.page_boundary,
                conditions=[node.done,
                            self.page_boundary.ready])
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
            try:
                self.on_enter_state(event_data)
            except:
                traceback.print_exc()
                pdb.post_mortem()
                raise
        State.enter(self, event_data)

    def exit(self, event_data):
        """ Call on_exit method on state object """
        log.debug("%s.exit '%s' callback.", self.__class__.__name__, self.tag)
        if hasattr(self, 'on_exit_state') and callable(self.on_exit_state):
            try:
                self.on_exit_state(event_data)
            except:
                traceback.print_exc()
                pdb.post_mortem()
                raise
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

    def log_row(row):
        log.debug((["{:06.2f} {:06.2f}".format(col['left'], col['width']) for col in row]))
        log.debug((["{: >13.13}".format(col['text']) for col in row]))

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
        print(self.data.consume_row()[0]['text'])

class Address(Section):
    def __init__(self, *args, **kwargs):
        log.debug(f"{self.__class__.__name__} {args} {kwargs}")
        super().__init__(*args, **kwargs)
        self.orgnization = ""
        self.address = []

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        self.orgnization = row[0]['text']
        self.num_after_org = ' '.join([col['text']
                                       for col in row[1:]
                                       if col['text']])

        row = self.data.consume_row()
        self.address.append(' '.join([col['text']
                                    for col in row
                                    if col['text']]))
        row = self.data.consume_row()
        self.address.append(' '.join([col['text']
                                      for col in row
                                      if col['text']]))
        print(f"org {self.orgnization} adr {self.address}")

class StatementPeriod(Section):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        dates = row[0]['text'].split(':')[1]
        start_date_string, stop_date_string = dates.split('-')
        self.start_date = start_date_string
        self.stop_date = stop_date_string
        print(f"dates {self.start_date} {self.stop_date}")

class BlockHeader(Section):
    def __init__(self, *args, lines=1, **kwargs):
        self.lines = lines
        super().__init__(*args, **kwargs)
        self.headers = []

    def on_enter_state(self, event_data):
        headers = [self.data.consume_row() for _ in range(self.lines)]
        for header in headers:
            Section.log_row(header)

        if len(headers) > 1:
            top = [col['text'] for col in headers[0]]
            bot = [col['text'] for col in headers[1]]
            self.headers.append(bot[0])

            split_top = top[1].split(' ')
            split_bot = bot[1].split(' ')

            self.headers.append(' '.join([split_top[0], split_bot[0]]))
            self.headers.append(' '.join([split_top[1], split_bot[1]]))
            self.headers.append(bot[2])
            self.headers.append(' '.join([top[4], bot[4]]))
            self.headers.append(' '.join([top[5], bot[5]]))



        print(self.headers)

class AccountsSummaryLine(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lines = []

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        Section.log_row(row)
        row = [r['text'] for r in row]
        line = []
        line.append(row[0])
        for r in row[1:]:
            if ' ' in r:
                line.extend(r.split(' '))
            else:
                line.append(r)
        print(line)

class FeesSummary(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        Section.log_row(row)

class AccountDetailHeader(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        Section.log_row(row)
        self.withdrawlOrDeposit = row[0]['text']
        print(self.withdrawlOrDeposit)

class AccountDetailYield(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        Section.log_row(row)
        row = self.data.consume_row()
        Section.log_row(row)
        row = self.data.consume_row()
        Section.log_row(row)

class AccountActivityHeader(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        Section.log_row(row)
        self.withdrawlOrDeposit = row[0]['text']
        row = self.data.consume_row()
        Section.log_row(row)
        self.headers = row[0]['text'].split(' ')
        self.headers = [*self.headers[0:2], ' '.join(self.headers[2:])]
        print(self.withdrawlOrDeposit)
        print(self.headers)

class AccountActivityLine(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lines = []

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        Section.log_row(row)
        row = [r['text'] for r in row if r['text']]
        line = row[0].split(' ')
        line.extend(row[1:])
        line = [*line[0:2], ' '.join(line[2:])]
        print(line)
        self.lines.append(line)

class PageBoundary(RegexMatchingSection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def on_enter_state(self, event_data):
        row = self.data.consume_row()
        Section.log_row(row)
        self.data.consume_page()
        row = self.data.consume_row()
        Section.log_row(row)
        row = self.data.consume_row()
        Section.log_row(row)




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
