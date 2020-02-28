from pprint import pprint
import json
import pdb
import traceback

from anytree import Node, RenderTree
from statemachine import StateMachine, State
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


class Institution(StateMachine):
    def __init__(self, doc):
        self.document = doc
        self.states = [
                       State('pre', initial=True),
                       State('post')
                       ]

class InstitutionWithSimpleHeaders(Institution):
    def __init__(self, headers, doc):
        super().__init__(doc)

class BECU(InstitutionWithSimpleHeaders):
    def __init__(self, headers, doc):
        super().__init__(doc)

class Section(Node):
    pass

class BECUPre(Section):
    pass
    # Statement Period:
    # address?

class BECUSummary(Section):
    def __init__(self, label):
        super().__init__()
        self.label = label


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

def regions(pdf='/Volumes/2019 Google Drive/Google Drive/foolscap/archive/Financial Accounts/BECU/2020/becu  2020-01-01 2020-01-31 littlecatz Estatement.pdf'):
    pdf_json = tabula.read_pdf(pdf, pages='all', output_format='json', multiple_tables=True, relative_area=True, area=[0,0,100,100], lattice=False, stream=True)
    #print(json.dumps(pdf_json, indent=2))

    sections = []
    section = { 'type': 'pre'}
    if is_becu(pdf_json):
        for page in pdf_json:
            for row in page['data']:
                for col in row:
                    section_type = is_becu_section(col['text'])
                    if section_type:
                        if section:
                            sections.append(section)
                        section = {}
                        section['type'] = col['text']
                        section['geom'] = col
                    else:
                        if section:
                            section.setdefault('text', []).append(col)

    if section:
        sections.append(section)
    pprint(sections)





if __name__ == '__main__':
    try:
        fire.Fire()
    except:
        traceback.print_exc()
        pdb.post_mortem()
