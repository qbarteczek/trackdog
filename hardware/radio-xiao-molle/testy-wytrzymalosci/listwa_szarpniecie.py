# Jedna listwa trzyma całą obudowę. Szarpnięcie obudowy od kamizelki (zaczepienie o gałąź) 60 N:
# mostki obu bloczków pchają listwę od kamizelki, rząd taśmy PALS trzyma ją pośrodku.
# Zginanie przez grubość listwy (3,2 mm), ścieżki wzdłuż listwy. Przy wstrząsach (15 N) SF 4 razy większy.
import numpy as np
OPIS = 'listwa MOLLE: szarpnięcie obudowy 60 N (zginanie na rzędzie taśmy)'
STL = 'listwa.stl'
WOKSEL = None
W_TUNELU = lambda x: np.abs(x) < 9.0
UTWIERDZENIE = lambda x, y, z: (y > 27) & (y < 48) & (z > 2.4)          # taśma na listwie
OBCIAZENIA = [
    dict(gdzie=lambda x, y, z: (y > 2) & (y < 23) & (z < 0.8) & W_TUNELU(x), sila=(0, 0, 30)),   # bloczek 1
    dict(gdzie=lambda x, y, z: (y > 52) & (y < 73) & (z < 0.8) & W_TUNELU(x), sila=(0, 0, 30)),  # bloczek 2 (ramiona grotu)
]
CYKLE = 'raz'
