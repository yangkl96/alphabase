# AUTOGENERATED! DO NOT EDIT! File to edit: ../../../nbdev_nbs/io/psm_reader/maxquant_reader.ipynb.

# %% auto 0
__all__ = ['parse_mod_seq', 'MaxQuantReader']

# %% ../../../nbdev_nbs/io/psm_reader/maxquant_reader.ipynb 3
import pandas as pd
import numpy as np
import numba
import copy

from alphabase.io.psm_reader.psm_reader import (
    PSMReaderBase, psm_reader_provider,
    psm_reader_yaml
)

@numba.njit
def parse_mod_seq(
    modseq:str,
    mod_sep:str='()',
    fixed_C57:bool=True,
    underscore_for_ncterm:bool=True,
)->tuple:
    """Extract modifications and sites from the modified sequence (modseq)

    Parameters
    ----------
    modseq : str
        modified sequence to extract modifications.

    mod_sep : str, optional
        separator to indicate the modification section. 
        Defaults to '()'

    fixed_C : bool
        If Carbamidomethyl@C is a fixed modification 
        and not displayed in the sequence. Defaults to True for MaxQuant.

    underscore_for_ncterm : bool
        If modseq starts and ends with underscores. 
        Defaults to True.

    Returns
    -------
    tuple
        str: modification names, separated by ';'
        
        str: modification sites, separated by ';'. 
            0 for N-term; -1 for C-term; 1 to N for normal modifications.
    """
    PeptideModSeq = modseq
    mod_list = []
    site_list = []
    site = PeptideModSeq.find(mod_sep[0])
    while site != -1:
        site_end = PeptideModSeq.find(mod_sep[1],site+1)+1
        if site_end < len(PeptideModSeq) and PeptideModSeq[site_end] == mod_sep[1]: 
            site_end += 1
        if underscore_for_ncterm: site_list.append(site-1)
        else: site_list.append(site)
        start_mod = site
        if start_mod > 0: start_mod -= 1
        mod_list.append(PeptideModSeq[start_mod:site_end])
        PeptideModSeq = PeptideModSeq[:site] + PeptideModSeq[site_end:]
        site = PeptideModSeq.find(mod_sep[0], site)

    # patch for phos. How many other modification formats does MQ have?
    site = PeptideModSeq.find('p') 
    while site != -1:
        mod_list.append(PeptideModSeq[site:site+2])
        site_list = [i-1 if i > site else i for i in site_list]
        if underscore_for_ncterm: site_list.append(site)
        else: site_list.append(site+1)
        PeptideModSeq = PeptideModSeq[:site] + PeptideModSeq[site+1:]
        site = PeptideModSeq.find('p', site)
        
    if fixed_C57:
        site = PeptideModSeq.find('C')
        while site != -1:
            if underscore_for_ncterm: site_list.append(site)
            else: site_list.append(site+1)
            mod_list.append('C'+"Carbamidomethyl (C)".join(mod_sep))
            site = PeptideModSeq.find('C',site+1)
    nAA = len(PeptideModSeq.strip('_'))
    return ';'.join(mod_list), ';'.join([str(i) if i <= nAA else '-1' for i in site_list])


class MaxQuantReader(PSMReaderBase):
    def __init__(self,
        *,
        column_mapping:dict = None,
        modification_mapping:dict = None,
        fdr = 0.01,
        keep_decoy = False,
        mod_sep = '()',
        underscore_for_ncterm=True,
        fixed_C57 = True,
        mod_seq_columns = ['Modified sequence'],
        **kwargs,
    ):
        super().__init__(
            column_mapping=column_mapping,
            modification_mapping=modification_mapping,
            fdr = fdr,
            keep_decoy = keep_decoy,
        )

        self.mod_sep = mod_sep
        self.underscore_for_ncterm = underscore_for_ncterm
        self.fixed_C57 = fixed_C57
        self._mod_seq_columns = mod_seq_columns
        self.mod_seq_column = 'Modified sequence'

    def _find_mod_seq_column(self, df):
        for mod_seq_col in self._mod_seq_columns:
            if mod_seq_col in df.columns:
                self.mod_seq_column = mod_seq_col
                break
        
    def _init_modification_mapping(self):
        self.modification_mapping = copy.deepcopy(
            psm_reader_yaml['maxquant'][
                'modification_mapping'
            ]
        ) # maxquant reader will modify the dict inplace

    def set_modification_mapping(self, modification_mapping: dict):
        super().set_modification_mapping(modification_mapping)
        self._extend_mod_brackets()
        self._reverse_mod_mapping()

    def _extend_mod_brackets(self):
        for key, mod_list in list(self.modification_mapping.items()):
            extend_mods = []
            for mod in mod_list:
                if mod[1] == '(':
                    extend_mods.append(f'{mod[0]}[{mod[2:-1]}]')
                elif mod[1] == '[':
                    extend_mods.append(f'{mod[0]}({mod[2:-1]})')

            self.modification_mapping[key].extend(extend_mods)
            
            self.modification_mapping[key].extend(
                [f'{mod[1:]}' for mod in mod_list if mod.startswith('_')]
            )
    
    def _translate_decoy(self, origin_df=None):
        if 'decoy' in self._psm_df.columns:
            self._psm_df.decoy = (
                self._psm_df.decoy == '-'
            ).astype(np.int8)

    def _init_column_mapping(self):
        self.column_mapping = psm_reader_yaml[
            'maxquant'
        ]['column_mapping']

    def _load_file(self, filename):
        df = pd.read_csv(filename, sep='\t')
        self._find_mod_seq_column(df)
        df = df[~pd.isna(df['Retention time'])]
        df.fillna('', inplace=True)
        # if 'K0' in df.columns:
        #     df['Mobility'] = df['K0'] # Bug in MaxQuant? It should be 1/K0
        # min_rt = df['Retention time'].min()
        return df

    def _load_modifications(self, origin_df: pd.DataFrame):
        (
            self._psm_df['mods'], 
            self._psm_df['mod_sites']
        ) = zip(
            *origin_df[self.mod_seq_column].apply(
                parse_mod_seq, mod_sep=self.mod_sep,
                fixed_C57=self.fixed_C57,
                underscore_for_ncterm=self.underscore_for_ncterm
            )
        )

psm_reader_provider.register_reader('maxquant', MaxQuantReader)
