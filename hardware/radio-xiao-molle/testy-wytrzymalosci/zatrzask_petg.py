# Grot listwy przy wsuwaniu: oba ramiona ściśnięte do szerokości tunelu (2 mm na ramię).
# Geometria grotu jak w meshcore-tracker/obudowa v3; zmienia się tylko długość listwy.
# STL: oś listwy = Y, główka y < 0, szczelina od y = 35,6, zaczepy przy y = 75,6.
import numpy as np
OPIS = 'listwa MOLLE (1 szt.), ściśnięcie grotu 2 mm na ramię - zdejmowanie/zakładanie'
STL = 'listwa-zatrzask.stl'
WOKSEL = None
UTWIERDZENIE = lambda x, y, z: y < 23.6                       # 12 mm przed szczeliną
TUNEL = 18.8 / 2
UGIECIE = 2.0
OBCIAZENIA = [
    dict(gdzie=lambda x, y, z: (y > 75.6) & (y < 77.7) & (x > TUNEL + 0.5), przemieszczenie=(-UGIECIE, None, None)),
    dict(gdzie=lambda x, y, z: (y > 75.6) & (y < 77.7) & (x < -TUNEL - 0.5), przemieszczenie=(UGIECIE, None, None)),
]
POMIN = lambda x, y, z: y > 72.6
CYKLE = 'wiele'
