# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/constants/isotope.ipynb (unless otherwise specified).

__all__ = ['abundance_convolution', 'one_element_dist', 'formula_dist', 'IsotopeDistribution']

# Cell
import numba
import numpy as np
import typing

from alphabase.constants.element import (
    MAX_ISOTOPE_LEN, EMPTY_DIST,
    CHEM_ISOTOPE_DIST, CHEM_MONO_IDX, CHEM_MONO_MASS,
    truncate_isotope, parse_formula
)

# Cell
@numba.njit
def abundance_convolution(
    d1:np.array,
    mono1:int,
    d2:np.array,
    mono2:int,
)->typing.Tuple[np.array, int]:
    '''
    If we have two isotope distributions,
    we can convolute them into one distribution.

    Args:
        d1 (np.array): isotope distribution to convolute.
        mono1 (int): mono position of d1.
        d2 (np.array): isotope distribution to convolute.
        mono2 (int): mono position of d2
    Returns:
        np.array: convoluted isotope distribution.
        int: new mono position.
    '''
    mono_idx = mono1 + mono2
    ret = np.zeros(MAX_ISOTOPE_LEN*2-1)
    for i in range(len(d1)):
        for j in range(len(d2)):
            ret[i+j] += d1[i]*d2[j]

    mono_idx, start, end = truncate_isotope(ret, mono_idx)
    return ret[start:end], mono_idx

# Cell
@numba.njit
def one_element_dist(
    elem: str,
    n: int,
    chem_isotope_dist: numba.typed.Dict,
    chem_mono_idx: numba.typed.Dict,
)->typing.Tuple[np.array, int]:
    '''
    Calculate the isotope distribution for
    an element and its numbers.

    Args:
        elem (str): element.
        n (int): element number.
        chem_isotope_dist (numba.typed.Dict): use `CHEM_ISOTOPE_DIST` as parameter.
        chem_mono_idx (numba.typed.Dict): use `CHEM_MONO_IDX` as parameter.
    Returns:
        np.array: isotope distribution of the element.
        int: mono position in the distribution
    '''
    if n == 0: return EMPTY_DIST.copy(), 0
    elif n == 1: return chem_isotope_dist[elem], chem_mono_idx[elem]
    tmp_dist, mono_idx = one_element_dist(elem, n//2, chem_isotope_dist, chem_mono_idx)
    tmp_dist, mono_idx = abundance_convolution(tmp_dist, mono_idx, tmp_dist, mono_idx)
    if n%2 == 0:
        return tmp_dist, mono_idx
    else:
        return abundance_convolution(tmp_dist, mono_idx, chem_isotope_dist[elem], chem_mono_idx[elem])

def formula_dist(
    formula: typing.Union[list, str]
)->typing.Tuple[np.array, int]:
    '''
    Generate the isotope distribution and the mono index for
    a given formula (as a list, e.g. `[('H', 2), ('C', 2), ('O', 1)]`),
    Args:
        formula (typing.Union[list, str]): chemical formula, could be str or list.
            If str: "H(1)N(2)O(3)".
            If list: "[('H',1),('H',2),('H',3)]".
    Returns:
        np.array: isotope distribution
        int: mono position
    '''
    if isinstance(formula, str):
        formula = parse_formula(formula)
    calc_dist = EMPTY_DIST.copy()
    mono_idx = 0
    for elem, n in formula:
        _dist, _mono = one_element_dist(elem, n, CHEM_ISOTOPE_DIST, CHEM_MONO_IDX)
        calc_dist, mono_idx = abundance_convolution(calc_dist, mono_idx, _dist, _mono)
    return calc_dist, mono_idx

# Cell

def _calc_one_elem_cum_dist(
    element_cum_dist:np.array,
    element_cum_mono:np.array
):
    """Pre-build element isotope abundance distribution for fast calculation

    Args:
        element_cum_dist (np.array): cumulated element abundance distribution
        element_cum_mono (np.array): cumulated element mono position in the distribution
    Returns:
        None. Added information inplace into element_cum_dist and element_cum_mono
    """
    for n in range(2, len(element_cum_dist)):
        (
            element_cum_dist[n],
            element_cum_mono[n]
        ) = abundance_convolution(
            element_cum_dist[n-1],
            element_cum_mono[n-1],
            element_cum_dist[1],
            element_cum_mono[1]
        )

class IsotopeDistribution:
    def __init__(self,
        max_elem_num_dict:dict = {
            'C': 2000,
            'H': 5000,
            'N': 1000,
            'O': 1000,
            'S': 200,
            'P': 200,
        }
    ):
        """Faster calculation of isotope abundance distribution by pre-defining
        isotope distribution tables.

        Args:
            max_elem_num_dict (dict, optional):
            Define the maximal number of the elements.
            Defaults to { 'C': 2000, 'H': 5000, 'N': 1000, 'O': 1000, 'S': 200, 'P': 200, },
            they are large enough for shotgun proteomics.
        Attributes:
            element_to_cum_dist_dict (dict): {element: cumulated isotope distribution array},
                and the cumulated isotope distribution array is a 2-D float np.array with
                shape (element_max_number, MAX_ISOTOPE_LEN).
            element_to_cum_mono_idx (dict): {element: mono position array of cumulated isotope distribution},
                and mono position array is a 1-D int np.array.
        """
        self.element_to_cum_dist_dict = {}
        self.element_to_cum_mono_idx = {}
        for elem, n in max_elem_num_dict.items():
            if n < 2: n = 2
            self.element_to_cum_dist_dict[elem] = np.zeros((n, MAX_ISOTOPE_LEN))
            self.element_to_cum_mono_idx[elem] = -np.ones(n,dtype=np.int64)
            self.element_to_cum_dist_dict[elem][0,:] = EMPTY_DIST.copy()
            self.element_to_cum_mono_idx[elem][0] = 0
            self.element_to_cum_dist_dict[elem][1,:] = CHEM_ISOTOPE_DIST[elem]
            self.element_to_cum_mono_idx[elem][1] = CHEM_MONO_IDX[elem]
            _calc_one_elem_cum_dist(
                self.element_to_cum_dist_dict[elem],
                self.element_to_cum_mono_idx[elem]
            )

    def calc_formula_distribution(self,
        formula: typing.List[typing.Tuple[str,int]],
    )->typing.Tuple[np.array, int]:
        """Calculate isotope abundance distribution for a given formula

        Args:
            formula (list of tuple(str,int)): chemical formula: "[('H',1),('H',2),('H',3)]".

        Returns:
            np.array: isotope abundance distribution
            int: mono isotope position in the distribution array
        """
        dist = EMPTY_DIST.copy()
        mono = 0
        for elem, n in formula:
            if elem in self.element_to_cum_dist_dict:
                # We have consider large enough number of elements.
                if n >= len(self.element_to_cum_mono_idx[elem]):
                    # Note that non-standard amino acids have 1000000
                    # C elements in AlphaBase.
                    n = len(self.element_to_cum_mono_idx[elem])-1
                dist, mono = abundance_convolution(
                    dist, mono,
                    self.element_to_cum_dist_dict[elem][n],
                    self.element_to_cum_mono_idx[elem][n],
                )
            else:
                dist, mono = abundance_convolution(
                    dist, mono, *one_element_dist(
                        elem,n,CHEM_ISOTOPE_DIST, CHEM_MONO_IDX
                    )
                )
        return dist, mono

