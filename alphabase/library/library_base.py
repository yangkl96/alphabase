# AUTOGENERATED! DO NOT EDIT! File to edit: nbdev_nbs/library/library_base.ipynb (unless otherwise specified).

__all__ = ['str_to_int', 'generate_modified_sequence', 'merge_precursor_fragment_df', 'SpecLibBase',
           'alpha_to_other_mod_dict']

# Cell
import pandas as pd
import numpy as np
import numba
import typing
import tqdm
import itertools

import alphabase.peptide.fragment as fragment

@numba.njit
def str_to_int(s):
    if s.startswith('-'):
        neg = True
        s = s[1:]
    else:
        neg = False
    final_index, result = len(s) - 1, 0
    for i,v in enumerate(s):
        result += (ord(v) - 48) * (10 ** (final_index - i))
    if neg:
        return -result
    else:
        return result

#@numba.njit #(cannot use numba for pd.Series)
def generate_modified_sequence(
    df_items:typing.Tuple, # must be ('sequence','mods','mod_sites')
    translate_mod_dict:dict=None,
    mod_sep='()'
):
    '''
    Translate `(sequence, mods, mod_sites)` into a modified sequence. Used by `df.apply()`.
    For example, `('ABCDEFG','Mod1@A;Mod2@E','1;5')`->`_A(Mod1@A)BCDE(Mod2@E)FG_`.
    Args:
        df_items (List): must be `(sequence, mods, mod_sites)`
        translate_mod_dict (dict): A dict to map alpha modification names to other software
        mod_seq (str): '[]' or '()', default '()'
    '''
    nterm = '_'
    cterm = '_'
    mod_seq = df_items[0]
    if df_items[1]:
        mods = df_items[1].split(';')[::-1]
        mod_sites = df_items[2].split(';')[::-1]
        if translate_mod_dict:
            mods = [translate_mod_dict[mod] for mod in mods]
        for site, mod in zip(mod_sites, mods):
            _site = int(site)
            if _site > 0:
                mod_seq = mod_seq[:_site] + mod_sep[0]+mod+mod_sep[1] + mod_seq[_site:]
            elif _site == -1:
                cterm += mod_sep[0]+mod+mod_sep[1]
            elif _site == 0:
                nterm += mod_sep[0]+mod+mod_sep[1]
            else:
                mod_seq = mod_seq[:_site] + mod_sep[0]+mod+mod_sep[1] + mod_seq[_site:]
    return nterm + mod_seq + cterm

# Cell
@numba.njit
def _get_frag_info_from_column_name(column:str):
    idx = column.find('_')
    frag_type = column[:idx]
    ch_str = column[idx+1:]
    charge = str_to_int(ch_str[:-1])
    if ch_str[-1] == '-':
        charge = -charge
    if len(frag_type)==1:
        loss_type = 'noloss'
    else:
        idx = frag_type.find('-')
        loss_type = frag_type[idx+1:]
        frag_type = frag_type[0]
    return frag_type, loss_type, charge

def _get_frag_info_column_names(columns:typing.List[str]):
    frag_types = []
    loss_types = []
    charges = []
    for column in columns:
        frag, loss, charge = _get_frag_info_from_column_name(column)
        frag_types.append(frag)
        loss_types.append(loss)
        charges.append(charge)
    return frag_types, loss_types, charges

def _get_frag_num(columns, rows, frag_len):
    frag_nums = []
    for r,c in zip(rows, columns):
        if c[0] in 'xyz':
            frag_nums.append(frag_len-r)
        else:
            frag_nums.append(r+1)
    return frag_nums

def _flatten(list_of_lists):
    '''
    Flatten a list of lists
    '''
    return list(
        itertools.chain.from_iterable(list_of_lists)
    )

def merge_precursor_fragment_df(
    precursor_df:pd.DataFrame,
    fragment_mass_df:pd.DataFrame,
    fragment_inten_df:pd.DataFrame,
    top_n_inten:int,
    frag_type_head:str='FragmentType',
    frag_mass_head:str='FragmengMz',
    frag_inten_head:str='RelativeIntensity',
    frag_charge_head:str='FragmentCharge',
    frag_loss_head:str='FragmentLossType',
    frag_num_head:str='FragmentNumber'
):
    '''
    Convert alphabase library into a single dataframe (library for other software)
    '''
    df = precursor_df.copy()
    frag_columns = fragment_mass_df.columns.values.astype('U')
    frag_type_list = []
    frag_loss_list = []
    frag_charge_list = []
    frag_mass_list = []
    frag_inten_list = []
    frag_num_list = []
    for start, end in tqdm.tqdm(df[['frag_start_idx','frag_end_idx']].values):
        intens = fragment_inten_df.loc[start:end-1,:].values
        masses = fragment_mass_df.loc[start:end-1,:].values
        sorted_idx = np.argsort(intens.reshape(-1))[-top_n_inten:][::-1]
        idx_in_df = np.unravel_index(sorted_idx, masses.shape)

        frag_len = end-start
        rows = np.arange(frag_len, dtype=np.int32)[idx_in_df[0]]
        columns = frag_columns[idx_in_df[1]]

        frag_types, loss_types, charges = _get_frag_info_column_names(columns)

        frag_nums = _get_frag_num(columns, rows, frag_len)

        frag_type_list.append(frag_types)
        frag_loss_list.append(loss_types)
        frag_charge_list.append(charges)
        frag_mass_list.append(masses[idx_in_df])
        frag_inten_list.append(intens[idx_in_df])
        frag_num_list.append(frag_nums)

    try:
        df[frag_type_head] = frag_type_list
        df[frag_mass_head] = frag_mass_list
        df[frag_inten_head] = frag_inten_list
        df[frag_charge_head] = frag_charge_list
        df[frag_loss_head] = frag_loss_list
        df[frag_num_head] = frag_num_list
        return df.explode([
            frag_type_head,
            frag_mass_head,
            frag_inten_head,
            frag_charge_head,
            frag_loss_head,
            frag_num_head
        ])
    except ValueError:
        # df.explode does not allow mulitple columns before pandas version 1.x.x.
        df[frag_type_head] = frag_type_list
        df = df.explode(frag_type_head)

        df[frag_mass_head] = _flatten(frag_mass_list)
        df[frag_inten_head] = _flatten(frag_inten_list)
        df[frag_charge_head] = _flatten(frag_charge_list)
        df[frag_loss_head] = _flatten(frag_loss_list)
        df[frag_num_head] = _flatten(frag_num_list)
        return df



# Cell
alpha_to_other_mod_dict = {
    "Carbamidomethyl@C": "Carbamidomethyl (C)",
    "Oxidation@M": "Oxidation (M)",
    "Phospho@S": "Phospho (STY)",
    "Phospho@T": "Phospho (STY)",
    "Phospho@Y": "Phospho (STY)",
    "GlyGly@K": "GlyGly (K)",
    "Acetyl@Protein N-term": "Acetyl (Protein N-term)",
}

class SpecLibBase(object):
    def __init__(self,
        charged_ion_types:str, # e.g. ['b_1+','b_2+','y_1+','y_2+', ...]
        min_frag_mz = 200, max_frag_mz = 2000,
        min_precursor_mz = 500, max_precursor_mz = 2000,
    ):
        self.charged_ion_types = charged_ion_types
        self._precursor_df:pd.DataFrame = None
        self._fragment_inten_df:pd.DataFrame = None
        self._fragment_mass_df:pd.DataFrame = None
        self.min_frag_mz = min_frag_mz
        self.max_frag_mz = max_frag_mz
        self.min_precursor_mz = min_precursor_mz
        self.max_precursor_mz = max_precursor_mz

    @property
    def precursor_df(self):
        return self._precursor_df

    @precursor_df.setter
    def precursor_df(self, df):
        self._precursor_df = df.reset_index(drop=True)
        if 'precursor_mz' in self._precursor_df.columns:
            self.clip_precursor_()

    @property
    def fragment_mass_df(self):
        return self._fragment_mass_df

    @property
    def fragment_inten_df(self):
        return self._fragment_inten_df

    def clip_precursor_(self):
        '''
        Clip self._precursor_df inplace
        '''
        self._precursor_df = self._precursor_df[
            (self._precursor_df['precursor_mz']>=self.min_precursor_mz)&
            (self._precursor_df['precursor_mz']<=self.max_precursor_mz)
        ]
        self._precursor_df.reset_index(drop=True, inplace=True)

    def clip_inten_by_fragment_mass_(self):
        '''
        Clip self._fragment_inten_df inplace. All clipped masses are set as zeros.
        '''
        self._fragment_inten_df[
            (self._fragment_mass_df<self.min_frag_mz)|
            (self._fragment_mass_df>self.max_frag_mz)
        ] = 0

    def clip_inten_by_fragment_mass(self)->pd.DataFrame:
        df = self._fragment_inten_df.copy()
        df[
            (self._fragment_mass_df<self.min_frag_mz)|
            (self._fragment_mass_df>self.max_frag_mz)
        ] = 0
        return df

    def load_precursor_df(self,
        precursor_files, **kargs
    ):
        self._load_precursor_df(precursor_files, **kargs)
        self.clip_precursor_()

    def _load_precursor_df(self, precursor_files, **kargs):
        '''
        All sub-class must reimplement this method
        '''
        raise NotImplementedError(
            f'Sub-class of "{self.__class__}" must re-implement "_load_precursor_df()"'
        )

    def load_fragment_df(self, **kargs):
        self.load_fragment_mass_df(**kargs)
        self.load_fragment_inten_df(**kargs)

    def load_fragment_inten_df(self, **kargs):
        '''
        All sub-class must reimplement this method.
        Fragment intensities can be predicted or from AlphaPept, or ...
        '''
        raise NotImplementedError(
            f'Sub-class of "{self.__class__}" must re-implement "load_fragment_inten_df()"'
        )

    def load_fragment_mass_df(self):
        self._fragment_mass_df = fragment.get_fragment_mass_dataframe(
            self._precursor_df, self.charged_ion_types
        )

    def save_hdf(self, hdf_file):
        raise NotImplementedError('') # we need alphabase.HDFFile for HDF files

    def to_single_df(self,
        translate_mod_dict:dict = alpha_to_other_mod_dict,
        keep_k_highest_inten:int=12
    )->pd.DataFrame:
        '''
        Convert alphabase library to diann (or Spectronaut) library dataframe
        Args:
            translate_mod_dict (dict): a dict map modifications from alphabase to other software. Default: build-in `alpha_to_other_mod_dict`
            keep_k_highest_inten (int): only keep highest fragment intensities for each precursor. Default: 12
        Return:
            pd.DataFrame: a single-file dataframe which contains precursors and fragments
        '''
        df = pd.DataFrame()
        df['ModifiedPeptide'] = self._precursor_df[
            ['sequence','mods','mod_sites']
        ].apply(
            generate_modified_sequence,
            axis=1,
            translate_mod_dict=translate_mod_dict,
            mod_sep='[]'
        )

        df['frag_start_idx'] = self._precursor_df['frag_start_idx']
        df['frag_end_idx'] = self._precursor_df['frag_end_idx']

        df['PrecursorCharge'] = self._precursor_df['charge']
        if 'predict_RT' in self._precursor_df.columns:
            df['iRT'] = self._precursor_df['predict_RT']
        else:
            df['iRT'] = self._precursor_df['RT']
        df['LabelModifiedSequence'] = df['ModifiedPeptide']
        df['StrippedPeptide'] = self._precursor_df['sequence']

        if 'protein_name' in self._precursor_df.columns:
            df['ProteinName'] = self._precursor_df['protein_name']
            df['UniprotID'] = df['ProteinName']
            df['ProteinGroups'] = df['ProteinName']

        if 'uniprot_id' in self._precursor_df.columns:
            df['UniprotID'] = self._precursor_df['uniprot_id']
            if 'ProteinName' not in df.columns:
                df['ProteinName'] = df['UniprotID']
                df['ProteinGroups'] = df['UniprotID']

        if 'genes' in self._precursor_df.columns:
            df['Genes'] = self._precursor_df['genes']

        if 'protein_group' in self._precursor_df.columns:
            df['ProteinGroups'] = self._precursor_df['protein_group']

        frag_inten = self.clip_inten_by_fragment_mass()

        df = merge_precursor_fragment_df(
            df,
            self._fragment_mass_df,
            frag_inten,
            top_n_inten=keep_k_highest_inten,
            frag_type_head='FragmentType',
            frag_mass_head='FragmengMz',
            frag_inten_head='RelativeIntensity',
            frag_charge_head='FragmentCharge',
            frag_loss_head='FragmentLossType',
            frag_num_head='FragmentNumber'
        )
        df = df[df['RelativeIntensity']>0]

        return df.drop(['frag_start_idx','frag_end_idx'], axis=1)
