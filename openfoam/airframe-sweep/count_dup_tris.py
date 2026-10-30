#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import struct, collections
import numpy as np

d = open('cad/v1/cfd_parallel/body.stl', 'rb').read()
n = struct.unpack('<I', d[80:84])[0]
a = np.frombuffer(d[84:84+n*50], dtype=np.uint8).reshape(n, 50)
tris = a[:, :48].copy().view(np.float32).reshape(n, 4, 3)[:, 1:, :].astype(np.float64)

keys = []
for t in tris:
    starts = [tuple(t[(i+j) % 3]) for i in range(3)]
    i = min(range(3), key=lambda k: starts[k])
    keys.append(tuple(np.round(np.vstack([t[(i+j) % 3] for j in range(3)]).ravel(), 5)))

cnt = collections.Counter(keys)
dist = collections.Counter(cnt.values())
print('total %d unique %d | multiplicity: %s' % (len(keys), len(cnt), dict(dist)))
