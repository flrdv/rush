# Rush

This is a master branch. Why there are 146 commits and no real job is done? I removed everything. After 2 months of development, I found a critical problem of my architecture. The only way to solve it - simplify arch from triple-rank to double-rank. Throw away cluster and make resolver not main, but additional system. Integrate functionality of cluster into the mainserver core. 

Branches:
  - master - main branch where all the features appear first
  - release-x.x.x - releases of webserver
  - for-history - old triple-rank system, that doesn't seems to be workable (I didn't test it completely)
