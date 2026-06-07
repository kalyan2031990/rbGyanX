"""
Module: rbgyanx/core/tcp
Layer: 1 (Core - Deterministic Analytical)
Purpose: Tumor Control Probability (TCP) model implementations

Allowed Dependencies:
- numpy, scipy, pandas
- Standard library

Forbidden Dependencies:
- UI frameworks (tkinter, PyQt, matplotlib.pyplot)
- AI/ML inference engines
- Mode controllers
- File I/O beyond data structures

Assumptions:
- All models assume photon therapy unless stated
- Parameters must be pre-validated by caller
- No applicability checking at this layer

Model Implementations:
- Poisson TCP (Webb & Nahum, 1993)
- LKB-adapted TCP (Okunieff et al., 1995)
- Logistic TCP (Brahme, 1984)
- EUD-based TCP (Niemierko, 1997)
"""

from rbgyanx.core.tcp.poisson import calculate_tcp_poisson
from rbgyanx.core.tcp.lkb import calculate_tcp_lkb
from rbgyanx.core.tcp.logistic import calculate_tcp_logistic
from rbgyanx.core.tcp.eud import calculate_tcp_eud

__all__ = [
    'calculate_tcp_poisson',
    'calculate_tcp_lkb',
    'calculate_tcp_logistic',
    'calculate_tcp_eud'
]
