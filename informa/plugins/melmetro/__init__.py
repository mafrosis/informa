import datetime

from . import alexa, exceptions
from ..base import InformaBasePlugin


class MelMetroPlugin(InformaBasePlugin):
    run_every = datetime.timedelta(minutes=5)

    def process(self):
        try:
            return alexa.melmetro(None, 'st kilda')
        except exceptions.APIError as e:
            self.logger.error(e)


# 721: 1 - East Coburg - South Melbourne Beach
# 761: 3/3a - Melbourne University - East Malvern
# 1083: 5 - Melbourne University - Malvern
# 898: 6 - Melbourne University - Glen Iris
# 991: 8 - Moreland - Toorak
# 3343: 11 - West Preston - Victoria Harbour Docklands
# 8314: 12 - Victoria Gardens - St Kilda
# 724: 16 - Melbourne University - Kew via St Kilda Beach
# 725: 19 - North Coburg - Flinders Street Station, City
# 1880: 30 - St Vincents Plaza - Docklands via La Trobe St
# 2903: 48 - North Balwyn - Victoria Harbour Docklands
# 868: 55 - West Coburg - Domain Interchange
# 887: 57 - West Maribyrnong - Flinders Street Station, City
# 897: 59 - Airport West - Flinders Street Station, City
# 909: 64 - Melbourne University - East Brighton
# 913: 67 - Melbourne University - Carnegie
# 940: 70 - Waterfront City Docklands -  Wattle Park
# 947: 72 - Melbourne University - Camberwell
# 958: 75 - Etihad Stadium Docklands - Vermont South
# 976: 78 - North Richmond - Balaclava via Prahran
# 1002: 82 - Moonee Ponds - Footscray
# 1881: 86 - Bundoora RMIT - Waterfront City Docklands
# 1041: 96 - East Brunswick - St Kilda Beach
# 722: 109 - Box Hill - Port Melbourne

# East Coburg
# South Melbourne Beach
# Melbourne University
# East Malvern
# Malvern
# Glen Iris
# Moreland
# Toorak
# West Preston
# Victoria Gardens
# Kew
# North Coburg
# St Vincents Plaza
# Docklands
# North Balwyn
# West Coburg
# Domain Interchange
# West Maribyrnong
# Flinders Street
# Flinders Street Station
# Airport West
# East Brighton
# Carnegie
# Wattle Park
# Camberwell
# Etihad
# Vermont South
# North Richmond
# Balaclava
# Moonee Ponds
# Footscray
# Bundoora
# East Brunswick
# St Kilda
# St Kilda Beach
# Box Hill
# Port Melbourne
