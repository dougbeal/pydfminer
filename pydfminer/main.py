from pprint import pprint
import json
import pdb
import traceback

from treelib import Node, Tree
from transitions import Machine
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



class Bank(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Section(Node):
    def __init__(self, *args, **kwargs):
        if 'tag' not in kwargs:
            kwargs['tag'] = self.__class__.__name__
        super().__init__(*args, **kwargs)

class OptionalSection(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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


# BECU = {
#     "Summary of Deposit Account Activity": {
#         { 'headers': {
#             'lines': 2 },
#          'accounts': {
#              'lines': -1 },

#             }
#                                             },
#     "Deposit Account Activity": {
#         },
#     "Deposit Account Activity (continued)":{
#         },

# }


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

    doc = PdfDocument(pdf_json)
    becu = Bank(tag="BECU", data=doc)
    doc.add_node(becu)

    initial = Section(tag="initial")
    doc.add_node(initial, parent=becu)
    doc.add_node(Address(), parent=initial)
    doc.add_node(StatementPeriod(), parent=initial)


    summary = OptionalSection(tag="deposit account summary")
    doc.add_node(summary, parent=becu)
    doc.add_node(BlockHeader(), parent=summary)
    doc.add_node(AccountsSummary(), parent=summary)

    doc.add_node(BlockHeader(), parent=summary)
    doc.add_node(FeesSummary(), parent=summary)


    summary = OptionalSection(tag="loan account summary")
    doc.add_node(summary, parent=becu)
    doc.add_node(BlockHeader(), parent=summary)
    doc.add_node(AccountsSummary(), parent=summary)


    detail = OptionalSection(tag="deposit account detail")
    doc.add_node(detail, parent=becu)

    account = AccountDetailHeader()
    doc.add_node(account, parent=detail)
    doc.add_node(AccountDetailYield(), parent=account)

    doc.show(line_type="ascii-em", reverse=False, idhidden=False, key=False)




if __name__ == '__main__':
    try:
        fire.Fire()
    except:
        traceback.print_exc()
        pdb.post_mortem()
