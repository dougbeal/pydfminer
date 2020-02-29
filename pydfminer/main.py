from pprint import pprint
import json
import pdb
import traceback
import re

from treelib import Node, Tree
from transitions import Machine, State
import fire
import tabula

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


class Document(Tree):
    def __init__(self, document):
        super().__init__()
        self.document = document


class PdfDocument(Document):
    def __init__(self, document):
        super().__init__(document)
        self.location = {
            'page': 0,
            'row': 0,
            'col': 0
            }

class Becu(PdfDocument):
    def __init__(self, document):
        super().__init__(document)
        self.machine = Machine()
        self.bank = Bank(tag="BECU", data=document)
        self.add_node(self.bank)

        section = Section(tag="initial")
        self.add_node(section, parent=self.bank)
        
        contents = [Address(), StatementPeriod()]
        for item in contents:
            self.add_node(item, parent=section)
        self.machine.initial = section

        linear_transitions = [section, *contents]

        for from_, to_ in zip(linear_transitions, linear_transitions[1:]):
            self.machine.add_transition(from_.tag, from_, to_)

        last = contents[-1]

        summary = OptionalSection(
            "Summary of Deposit",
            tag="deposit account summary"
            )
        self.add_node(summary, parent=self.bank)

        self.machine.add_transition(last.tag, last, summary,
                                    conditions=[last.done,
                                                summary.ready])
        
        self.add_node(BlockHeader(), parent=summary)
        self.add_node(AccountsSummary(), parent=summary)

        self.add_node(BlockHeader(), parent=summary)
        self.add_node(FeesSummary(), parent=summary)


        summary = OptionalSection(
            "Summary of Loan",
            tag="loan account summary"
            )
        self.add_node(summary, parent=self.bank)
        self.add_node(BlockHeader(), parent=summary)
        self.add_node(AccountsSummary(), parent=summary)


        detail = OptionalSection(tag="deposit account detail")
        self.add_node(detail, parent=self.bank)

        account = AccountDetailHeader()
        self.add_node(account, parent=detail)
        self.add_node(AccountDetailYield(), parent=account)

        # OptionalPageHeader
        # PageFooter

    def add_node(self, node, parent=None):
        super().add_node(node, parent=parent)
        self.machine.add_state(node)


class NodeState(State, Node):
    def __init__(self, *args, **kwargs):
        if 'tag' not in kwargs:
            kwargs['tag'] = self.__class__.__name__
        name = kwargs.get('name', kwargs['tag'])
        Node.__init__(self, *args, **kwargs)
        State.__init__(
            self,
            name,
            on_enter=kwargs.get('on_enter'),
            on_exit=kwargs.get('on_exit'),
            ignore_invalid_triggers=kwargs.get('ignore_invalid_triggers')
            )        

class Bank(NodeState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Section(NodeState):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def ready(text):
        return True

    def done():
        return False

class OptionalSection(Section):
    def __init__(self, *args, section_regex, **kwargs):
        super().__init__(*args, **kwargs)
        self.pattern = re.compile(section_regex)

    def ready(text):
        search = self.pattern.search(text)
        return search != None

    def done():
        return False    

class Address(Section):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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



def is_becu(pages):
    for page in pages:
        for row in page['data']:
            for col in row:
                if 'becu' in col['text'].lower():
                    return True
    return False

def is_becu_section(text):
    for section_keyword in ['summary of', 'deposit account activity', 'loan account activity']:
        if text.lower().startswith(section_keyword):
            return section_keyword.split(' ')[0]
    return False

def process(pdf='/Volumes/2019 Google Drive/Google Drive/foolscap/archive/Financial Accounts/BECU/2020/becu  2020-01-01 2020-01-31 littlecatz Estatement.pdf'):
    pdf_json = tabula.read_pdf(pdf, pages='all', output_format='json', multiple_tables=True, relative_area=True, area=[0,0,100,100], lattice=False, stream=True)
    #print(json.dumps(pdf_json, indent=2))

    doc = Becu(pdf_json)
    doc.show(line_type="ascii-em", reverse=False, idhidden=False, key=False)
    doc.machine.initial




if __name__ == '__main__':
    try:
        fire.Fire()
    except:
        traceback.print_exc()
        pdb.post_mortem()
