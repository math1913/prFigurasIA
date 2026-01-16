import xml.etree.ElementTree as ET
from datetime import datetime
import time
# Writes in <value></value> tags in 'conditions_admina.xml' file the string parameter
def writeValor(texto: str):

    # Load the xml
    tree = ET.parse('/opt/Admira/share/conditions/biomax.xml')
    root = tree.getroot()

    # Finds condition tag
    condition = root.find('condition')
    # Finds value tag
    value = condition.find('value')
    value.text = texto

    condition.set("id", str(4))
    
    condition.set("tstamp", str(int(time.time())))


    tree.write('/opt/Admira/share/conditions/biomax.xml')