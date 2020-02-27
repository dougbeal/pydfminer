import json
import pdb
import traceback
from pprint import pprint

import tabula
import fire

"""
# institution classifier
## bank
- page
- statement period
- entitity
- accounts
- fees
- deposits
- withdrawls

### becu [pdf parse]
## financial services
### square [connect to api?]
### stripe
### paypal
"""

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
