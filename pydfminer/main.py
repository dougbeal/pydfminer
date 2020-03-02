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
logging.getLogger('transitions').setLevel(logging.INFO)

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
        log.debug(f"state {self.state}")
        previous_state = None
        # no self-transitions alowed
        while self.state != 'terminus' and previous_state != self.state:
            previous_state = self.state
            for outgoing in self.machine.get_triggers(self.state):
                log.debug(f"    trigger {outgoing}")
                self.machine.trigger(outgoing)
        log.debug(f"run complete state {self.state} prev {previous_state}")

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
            tag="summary deposit account"
            )
        section_transitions.append(last)

        last = self.section_summary(
            section_transitions,
            regex="Summary of Loan",
            tag="summary loan account",
            fee_section=False
            )
        section_transitions.append(last)

        last = self.section_detail(
            section_transitions,
            regex="Deposit Account",
            tag="deposit account"
            )
        section_transitions.append(last)

        last = self.section_detail(
            section_transitions,
            regex="Loan Account",
            tag="loan account"
            )
        section_transitions.append(last)

        # todo: add page breaks
        #   contues to sections

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

    def page_bounary(self):
        pass

    def section_summary(self, incomming, regex, tag, fee_section=True):
        summary = OptionalSection(section_regex=regex, tag=tag, data=self)
        self.add_node(summary, parent=self.bank)

        for last in incomming:
            self.machine.add_transition(
                last.tag, last, summary,
                conditions=[last.done,
                            summary.ready]
                )

        self.add_node(BlockHeader(data=self), parent=summary)
        last = self.add_node(AccountsSummary(data=self), parent=summary)

        if fee_section:
            self.add_node(BlockHeader(data=self), parent=summary)
            last = self.add_node(FeesSummary(data=self), parent=summary)
        return last

    def section_detail(self, incomming, regex, tag):
        detail = OptionalSection(section_regex=regex, tag=tag, data=self)
        self.add_node(detail, parent=self.bank)

        for last in incomming:
            self.machine.add_transition(
                last.tag, last, detail,
                conditions=[last.done,
                            detail.ready]
                )

        account = AccountDetailHeader(data=self)
        self.add_node(account, parent=detail)
        last = self.add_node(AccountDetailYield(data=self), parent=account)
        return last

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
        log.debug("%s.enter callback.", self.__class__.__name__)
        if hasattr(self, 'on_enter_state') and callable(self.on_enter_state):
            self.on_enter_state(event_data)
        State.enter(self, event_data)

    def exit(self, event_data):
        """ Call on_exit method on state object """
        log.debug("%s.exit callback.", self.__class__.__name__)        
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

    def ready(self):
        log.debug(f"{self.__class__.__name__} is ready")
        return True

    def done(self):
        log.debug(f"{self.__class__.__name__} is done")        
        return True

class OptionalSection(Section):
    def __init__(self, *args, section_regex, **kwargs):
        super().__init__(*args, **kwargs)
        self.pattern = re.compile(section_regex)

    def ready(self):
        search = None
        for col in self.data.row():
            search = self.pattern.search(col.text)
            if search:
                break
        return search != None

    def done(self):
        return False

class Address(Section):
    def __init__(self, *args, **kwargs):
        log.debug(f"{self.__class__.__name__} {args} {kwargs}")
        super().__init__(*args, **kwargs)
        self.done = False


    def on_enter_state(self, event_data):
        print(self.data.consume_row())
        print(self.data.consume_row())        
        print(self.data.consume_row())        
        self.done = True
    
    def done(self):
        return self.done   

class StatementPeriod(Section):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class BlockHeader(Section):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class AccountsSummary(Section):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class FeesSummary(Section):
    pass

class AccountDetailHeader(Section):
    pass

class AccountDetailYield(Section):
    pass


def process(pdf='/Volumes/2019 Google Drive/Google Drive/foolscap/archive/Financial Accounts/BECU/2020/becu  2020-01-01 2020-01-31 littlecatz Estatement.pdf'):
    pdf_json = tabula.read_pdf(pdf, pages='all', output_format='json', multiple_tables=True, relative_area=True, area=[0,0,100,100], lattice=False, stream=True)
    #print(json.dumps(pdf_json, indent=2))

    doc = Becu(pdf_json)
    log.debug(doc.machine.states.keys())
    log.debug(doc.machine.get_transitions())    
    #doc.show(line_type="ascii-em", reverse=False, idhidden=False, key=False)
    doc.run()
    #pprint(doc.state)
    doc.show(line_type="ascii-em", reverse=False, idhidden=False, key=False)    


if __name__ == '__main__':
    try:
        fire.Fire()
    except:
        traceback.print_exc()
        pdb.post_mortem()
