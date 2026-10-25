## PEAD topp/topp – ødelegger strukket-grensen avkastningen?
_Kode: signaltool/backtest/pead_stretch.py (kjør med PYTHONPATH=.). Samme hendelser som pead.py. Strukket ved inngang (d0+1): 5d ≥ +10 % ELLER 20d ≥ +25 % ELLER ≥ 25 % over 50d-snitt. Netto = vs SPY minus 0,2 %. HAC t på kvartalssnitt._

| Periode | Gruppe | n | 60d netto vs SPY | median | t |
|---|---|---|---|---|---|
| IS 2006–15 | strukket | 495 | +2.65 % | +2.16 % | 2.4 |
| IS 2006–15 | ikke strukket | 699 | +2.16 % | +2.09 % | 3.8 |
| OOS 2016–26 | strukket | 579 | +4.63 % | +2.50 % | 3.8 |
| OOS 2016–26 | ikke strukket | 746 | +0.65 % | +0.38 % | 0.7 |
| Diff strukket − ikke | IS | 40 kv. | +0.09 pp | | 0.1 |
| Diff strukket − ikke | OOS | 42 kv. | +4.31 pp | | 3.3 |

Konklusjon: grensen gir ingen gevinst i noen periode og fjerner 43 % av hendelsene. Strukket er ikke sikkert bedre (IS-diff ≈ 0), bare ikke dårligere.
Forbehold: survivorship (dagens S&P 500-medlemmer) blåser trolig opp vinnere, mest for aksjer som allerede har steget.
