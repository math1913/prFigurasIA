import xml.etree.ElementTree as ET
from datetime import datetime
import time
# Writes in <value></value> tags in 'conditions_admina.xml' file the string parameter
# Windows path: 'C:/admira/conditions/biomax.xml'
# Ubuntu path: '/opt/Admira/share/conditions/biomax.xml'

def writeValor(texto: str):
    t = 20
    # Load the xml
    tree = ET.parse('C:/admira/conditions/biomax.xml')
    root = tree.getroot()

    # Finds condition tag
    condition = root.find('condition')
    # Finds value tag
    value = condition.find('value')

    # Si no es la misma figura, o no pasaron t segundos no cambia el xml
    if (texto != value.text) or ((int(time.time()) - int(condition.get('tstamp'))) > t):
        value.text = texto

        condition.set("id", str(4))
        
        condition.set("tstamp", str(int(time.time())))

        tree.write('C:/admira/conditions/biomax.xml')