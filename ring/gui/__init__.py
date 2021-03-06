from sympy.physics.units import *
from sympy import S
from .stack_ring import StkRingWidget
from ._image_loading import *

One = S.One

pix = pixel = pixels = Quantity("pixel")
pixel.set_dimension(One)
pixel.set_scale_factor(One)

# sussex colors
SUSSEX_FLINT = '#013035'
SUSSEX_COBALT_BLUE = '#1E428A'
SUSSEX_MID_GREY = '#94A596'
SUSSEX_FUSCHIA_PINK = '#EB6BB0'
SUSSEX_CORAL_RED = '#DF465A'
SUSSEX_TURQUOISE = '#00AFAA'
SUSSEX_WARM_GREY = '#D6D2C4'
SUSSEX_SUNSHINE_YELLOW = '#FFB81C'
SUSSEX_BURNT_ORANGE = '#DC582A'
SUSSEX_SKY_BLUE = '#40B4E5'

SUSSEX_NAVY_BLUE = '#1B365D'
SUSSEX_CHINA_ROSE = '#C284A3'
SUSSEX_POWDER_BLUE = '#7DA1C4'
SUSSEX_GRAPE = '#5D3754'
SUSSEX_CORN_YELLOW = '#F2C75C'
SUSSEX_COOL_GREY = '#D0D3D4'
SUSSEX_DEEP_AQUAMARINE = '#487A7B'
