"""Offline verification of the delivered BOE result files; no downloads or training.
Usage from the archive root: python codigo/verificar_anexo.py
Requires NumPy and pandas. Reports are printed; original results are never modified.
"""
from pathlib import Path
import ast
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODELS = ['BETO', 'RoBERTalex', 'MEL', 'MrBERT-legal']
checks = []


def check(label, condition):
    if not condition:
        raise ValueError('FAILED: ' + label)
    checks.append(label)


def close(a, b, tolerance=0.000501):
    return bool(np.allclose(a, b, atol=tolerance, rtol=0))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = ROOT / 'resultados'
    extra = ROOT / 'analisis_complementario'
    lengths = pd.read_csv(data / 'longitudes_por_documento.csv', dtype={'issue_date': str})
    meta = pd.read_csv(data / 'muestra_boe_metadatos.csv', dtype={'issue_date': str})
    terms = pd.read_csv(ROOT / 'datos/terminos_juridicos_125.csv')
    detail = pd.read_csv(data / 'fragmentacion_terminos_detalle.csv')
    wide = pd.read_csv(data / 'fragmentacion_terminos_formato_ancho.csv')
    length_summary = pd.read_csv(data / 'tabla_longitudes_resumen.csv').set_index('tokenizer')
    frag_summary = pd.read_csv(data / 'tabla_fragmentacion_resumen.csv').set_index('tokenizer')
    frag_categories = pd.read_csv(data / 'fragmentacion_por_categoria.csv').set_index(['tokenizer','categoria'])
    manifest = json.loads((data / 'manifiesto_reproducibilidad.json').read_text())
    check('400 unique identifiers in metadata and lengths',
          len(meta) == len(lengths) == 400 and not meta.identifier.duplicated().any()
          and not lengths.identifier.duplicated().any()
          and set(meta.identifier) == set(lengths.identifier))
    fields = ['identifier', 'issue_date', 'year', 'section_code', 'section_name',
              'department_name', 'char_count', 'word_count']
    pd.testing.assert_frame_equal(meta[fields].sort_values('identifier').reset_index(drop=True),
                                  lengths[fields].sort_values('identifier').reset_index(drop=True))
    check('Metadata and length-table descriptions match document by document', True)
    check('80 documents per year from 2021 to 2025',
          lengths.groupby('year').size().to_dict() == {y:80 for y in range(2021,2026)})
    date_counts = lengths.groupby('issue_date').size()
    check('40 dates: 38 with 10, one with 9 and one with 11 documents',
          len(date_counts)==40 and date_counts.value_counts().to_dict()=={10:38,9:1,11:1})
    check('Section counts', meta.section_code.value_counts().to_dict()=={'2A':111,'1':100,'2B':96,'3':87,'T':6})
    check('125 unique legal expressions', len(terms)==125 and terms.termino.nunique()==125)
    check('500 unique expression-tokenizer results',
          len(detail)==500 and not detail.duplicated(['termino','tokenizer']).any()
          and set(detail.termino)==set(terms.termino) and set(detail.tokenizer)==set(MODELS))
    check('125 rows in wide fragmentation table',len(wide)==125 and wide.termino.nunique()==125)
    for model in MODELS:
        values = lengths['tokens_'+model].to_numpy()
        check(model+': valid positive integer token counts',
              np.isfinite(values).all() and (values>0).all() and (values==values.astype(int)).all())
        row=length_summary.loc[model]
        q=np.percentile(values,[50,90,95],method='linear')
        check(model+': published length statistics',
              close(q,row[['median','p90','p95']].to_numpy(dtype=float))
              and int(row['n'])==400 and int(row['min'])==values.min() and int(row['max'])==values.max()
              and all(close(100*np.mean(values>n),row['pct_gt_'+str(n)]) for n in [512,4096,8192]))
        g=detail[detail.tokenizer==model].set_index('termino').sort_index()
        w=wide.set_index('termino').loc[g.index]
        check(model+': pieces and counts match both fragmentation tables',
              close(g.subtokens,w['subtokens_'+model],0)
              and (g.token_pieces==w['pieces_'+model]).all()
              and all(len(p.split(' | '))==n for p,n in zip(g.token_pieces,g.subtokens)))
        check(model+': fragmentation arithmetic',
              close(g.subtokens_per_word,g.subtokens/g.orthographic_words,1e-12)
              and close(g.excess_subtokens,g.subtokens-g.orthographic_words,0)
              and (g.fragmented==(g.subtokens>g.orthographic_words)).all())
        s=frag_summary.loc[model]
        expected=[len(g),g.subtokens.mean(),g.subtokens.median(),
                  np.percentile(g.subtokens,90,method='linear'),g.subtokens_per_word.mean(),
                  g.subtokens_per_word.median(),100*g.fragmented.mean(),g.excess_subtokens.mean()]
        cols=['n_terms','mean_subtokens','median_subtokens','p90_subtokens','mean_subtokens_per_word',
              'median_subtokens_per_word','pct_fragmented','mean_excess_subtokens']
        check(model+': published fragmentation summary',close(expected,s[cols].to_numpy(dtype=float)))
        for category,c in g.groupby('categoria'):
            published=frag_categories.loc[(model,category)]
            computed=[len(c),c.subtokens_per_word.mean(),c.subtokens_per_word.median(),100*c.fragmented.mean()]
            check(model+': category summary '+category,
                  close(computed,published[['n_terms','mean_subtokens_per_word','median_subtokens_per_word','pct_fragmented']].to_numpy(dtype=float)))
    matrix=pd.read_csv(data/'svm_matriz_confusion.csv',index_col=0)
    matrix.index=matrix.index.astype(str); matrix.columns=matrix.columns.astype(str)
    a=matrix.to_numpy(dtype=float); tp=np.diag(a); support=a.sum(axis=1)
    precision=tp/a.sum(axis=0); recall=tp/support; f1=2*precision*recall/(precision+recall)
    svm=json.loads((data/'svm_resumen.json').read_text())
    report=pd.read_csv(data/'svm_metricas_por_clase.csv',dtype={'class_code':str}).set_index('class_code')
    check('SVM metric file agrees with confusion matrix',
          all(close([precision[i],recall[i],f1[i],support[i]],
                    report.loc[label,['precision','recall','f1','support']].to_numpy(dtype=float),0.000051)
              for i,label in enumerate(matrix.index)))
    check('SVM global metrics agree with confusion matrix',
          close([f1.mean(),tp.sum()/a.sum(),recall.mean()],
                [svm['macro_f1'],svm['accuracy'],svm['balanced_accuracy']],1e-12))
    eligible=meta.section_code.isin(svm['classes'])
    check('Temporal split: 316 training, 78 test, six excluded documents',
          int((eligible & (meta.year<2025)).sum())==svm['n_train']==316
          and int((eligible & (meta.year==2025)).sum())==svm['n_test']==int(a.sum())==78
          and int((~eligible).sum())==6)
    check('Original manifest agrees with sample and SVM results',
          manifest['sampling']['actual_docs']==400 and manifest['sampling']['n_issue_dates']==40
          and manifest['svm']==svm and manifest['term_fragmentation']['n_terms']==125)
    for p in (ROOT/'codigo').glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8')); check('Python syntax: '+p.name,True)
    previous=json.loads((extra/'manifiesto_analisis_complementario.json').read_text())
    for name,digest in previous['sha256'].items():
        p=(ROOT/'codigo'/name) if name.endswith('.py') else data/name
        check('Original complementary-analysis input hash: '+name,sha(p)==digest)
    with tempfile.TemporaryDirectory(prefix='boe_verify_') as tmp:
        subprocess.run([sys.executable,str(ROOT/'codigo/analisis_complementario.py'),str(data),tmp],
                       check=True,capture_output=True,text=True)
        out=Path(tmp)
        for p in extra.glob('*.csv'):
            pd.testing.assert_frame_equal(pd.read_csv(p),pd.read_csv(out/p.name),check_exact=False,atol=1e-10,rtol=1e-12)
            check('Recalculated complementary results: '+p.name,True)
        check('Section III errors match recalculation',
              json.loads((extra/'errores_seccion_III.json').read_text())==json.loads((out/'errores_seccion_III.json').read_text()))
    sums=ROOT/'SHA256SUMS.txt'
    if sums.exists():
        for line in sums.read_text().splitlines():
            digest,name=line.split('  ',1)
            check('Archive integrity: '+name,sha(ROOT/name)==digest)
    result={'status':'PASS','checks_passed':len(checks),'python':platform.python_version(),
            'numpy':np.__version__,'pandas':pd.__version__,'checks':checks,
            'scope':'Offline arithmetic consistency and package integrity. No downloads, tokenization, or retraining.',
            'limitations':['Full BOE text not included; stored text hashes cannot be recalculated here.',
                           'Per-document SVM predictions and fitted classifier are not included.',
                           'The original requirements file gives version ranges, not a complete environment lockfile.']}
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
