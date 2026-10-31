# Benchmark do nini-datagen

N = 5,000,000 · 16 threads · Python 3.11.14 · Polars 2.1.0 · Windows-10-10.0.26200-SP0 · DG_CLANGCL='1' DG_NATIVE=''

| gerador | 1 thread | 16 threads | MVP 1 thread | MVP 16 threads | situação |
|---|---:|---:|---:|---:|---|
| integer | 1.38 | 1.39 | 1.2 | 1.1 | **1.15x o MVP** |
| uniform | 1.85 | 1.87 | 1.3 | 1.5 | **1.42x o MVP** |
| normal | 4.91 | 1.41 | 3.5 | 1.4 | **1.40x o MVP** |
| lognormal | 7.34 | 1.74 | 4.3 | 1.6 | **1.71x o MVP** |
| boolean | 0.09 | 0.07 | 0.2 | 1.2 | ok |
| date | 1.51 | 1.60 | 1.2 | 1.3 | **1.26x o MVP** |
| datetime | 1.89 | 1.93 | 1.2 | 1.3 | **1.58x o MVP** |
| choice | 2.78 | 1.51 |  |  | sem referência |
| sex | 2.87 | 1.73 | 4.3 | 2.6 | ok |
| age | 1.65 | 1.02 | 2.1 | 1.6 | ok |
| first_name | 3.10 | 1.50 | 5.4 | 2.7 | ok |
| first_name_by_sex | 8.09 | 5.97 | 6.2 | 3.4 | **1.30x o MVP** |
| last_name | 3.56 | 1.44 | 4.9 | 3.0 | ok |
| full_name | 55.34 | 30.29 |  |  | sem referência |
