"""Truth-blind average-linkage starting-tree witness."""
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
def build_tree(problem):
 seq=problem["alignment"]; n=len(seq); d=np.zeros((n,n))
 for i in range(n):
  for j in range(i): d[i,j]=d[j,i]=sum(a!=b for a,b in zip(seq[i],seq[j]))/len(seq[i])
 z=linkage(squareform(d),method="average"); nodes={i:problem["taxa"][i] for i in range(n)}
 for k,row in enumerate(z): nodes[n+k]=f"({nodes[int(row[0])]},{nodes[int(row[1])]})"
 return nodes[2*n-2]+";"
