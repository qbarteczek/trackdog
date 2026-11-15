# Podstawa: szarpnięcie obudowy od kamizelki 60 N. Listwa opiera się o mostki (2 mm) pod tunelami
# w obu bloczkach. STL w położeniu do druku (na stojąco): x = x, y_druk = -z, z_druk = y obudowy.
# Utwierdzenie: obrzeże pod wiekiem (tam ciągnie obudowa); obciążenie: mostki, siła w stronę kamizelki.
import numpy as np
OPIS = 'podstawa: szarpnięcie 60 N, mostki pod listwą w bloczkach'
STL = 'podstawa.stl'
WOKSEL = 0.9
WARSTW = 2
MOSTEK = lambda x, y, z: (y > -2.2) & (y < -0.9) & (np.abs(x - 22) < 9.0)
UTWIERDZENIE = lambda x, y, z: y < -30.1
OBCIAZENIA = [
    dict(gdzie=lambda x, y, z: MOSTEK(x, y, z) & (z > 9.5) & (z < 31.8), sila=(0, 30, 0)),
    dict(gdzie=lambda x, y, z: MOSTEK(x, y, z) & (z > 59.3) & (z < 81.6), sila=(0, 30, 0)),
]
CYKLE = 'raz'
