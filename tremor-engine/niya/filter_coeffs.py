import numpy as np
from scipy import signal
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from shared.constants import SAMPLING_RATE_HZ, BUTTERWORTH_ORDER, BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ

def get_butterworth_coefficients():
    order = BUTTERWORTH_ORDER // 2
    b, a = signal.butter(order, [BANDPASS_LOW_HZ, BANDPASS_HIGH_HZ], btype='bandpass', fs=SAMPLING_RATE_HZ)
    return b, a

if __name__ == "__main__":
    b, a = get_butterworth_coefficients()
    print("Butterworth b:", [round(x, 6) for x in b])
    print("Butterworth a:", [round(x, 6) for x in a])
    
