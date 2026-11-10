# C2PA-Testbilder

`plain.*` sind 64×48-Bilder aus Qt, `signed.*` dieselben Bilder, mit der
c2pa-Bibliothek (c2pa-python 0.37) signiert. Die Zertifikatskette war ein
selbst erzeugtes Wegwerf-Paar (Test Root / Test Signer), nur für diese Dateien.

`tests/test_c2pa_cleaner.py` prüft damit: Nach dem Entfernen findet die
c2pa-Bibliothek kein Manifest mehr, und die Datei ist bit-identisch zu
`plain.*`.
