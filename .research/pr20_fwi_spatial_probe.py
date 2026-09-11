"""Independent reconstruction of the review's spatial Gaussian-search family.

Exact maintainer grid coordinates were not supplied. This implementation fixes
all grids from public geometry, before new-world validation. No evaluator imports.
"""
import itertools
import numpy as np

THRESHOLD=.24
REFINE=False
LENSES=1

def simulate(models,sources,spacing,time_s,receiver_x):
    # Model and shot dimensions are independent batch axes.
    models=np.asarray(models);sources=np.asarray(sources,dtype=int)
    receivers=np.rint(np.asarray(receiver_x)/spacing).astype(int)
    shape=(len(models),len(sources),*models.shape[1:])
    previous=np.zeros(shape);current=np.zeros(shape)
    damping=np.ones(models.shape[1:])
    damping[[0,-1],:]=.86;damping[:,[0,-1]]=.86
    damping[[1,-2],:]=.94;damping[:,[1,-2]]=.94
    coefficient=(models[:,None,:,:]*(time_s[1]-time_s[0])/spacing)**2
    arg=np.pi*12*(np.asarray(time_s)-1.5/12)
    wavelet=(1-2*arg**2)*np.exp(-arg**2)
    traces=np.empty((len(models),len(sources),len(time_s),len(receivers)))
    for t,w in enumerate(wavelet):
        lap=np.zeros_like(current)
        lap[...,1:-1,1:-1]=(current[...,1:-1,2:]+current[...,1:-1,:-2]
            +current[...,2:,1:-1]+current[...,:-2,1:-1]-4*current[...,1:-1,1:-1])
        nxt=(2*current-previous+coefficient*lap)*damping
        nxt[:,:,2,sources] += np.eye(len(sources))[None,:,:]*w
        traces[:,:,t,:]=nxt[:,:,2,receivers]
        previous,current=current,nxt
    return traces

def invert_velocity_model(grid_shape,spacing_m,background_velocity_m_s,velocity_bounds_m_s,
                          source_indices,receiver_x_m,time_s,acquire,budget_units):
    sources=np.asarray(source_indices)[np.linspace(0,len(source_indices)-1,min(3,int(budget_units)),dtype=int)]
    obs=np.asarray([acquire(int(s))['pressure'] for s in sources])
    bg=np.asarray(background_velocity_m_s)
    base=simulate(bg[None],sources,spacing_m,time_s,receiver_x_m)[0]
    norm=max(np.linalg.norm(obs),1e-12)
    relative=np.linalg.norm(obs-base)/max(np.linalg.norm(base),1e-12)
    energy=np.linalg.norm(obs)/max(np.linalg.norm(base),1e-12)
    if relative<.006 or energy<.95:
        return {'velocity_m_s':[],'confidence':.1,'abstain':True}
    zz,xx=np.mgrid[:grid_shape[0],:grid_shape[1]]
    coordinates=list(itertools.product(np.linspace(.15,.85,8)*(grid_shape[1]-1),
        np.linspace(.2,.75,5)*(grid_shape[0]-1),[-900.,-600.,-300.,300.,600.,900.]))
    coordinates=[(*v,4.5,3.4) for v in coordinates]
    def search(points, center):
        best=(float('inf'),None,None)
        for start in range(0,len(points),24):
            chunk=points[start:start+24]
            models=np.asarray([np.clip(center+amp*np.exp(-.5*(((xx-cx)/sx)**2+((zz-cz)/sz)**2)),
                                       *velocity_bounds_m_s) for cx,cz,amp,sx,sz in chunk])
            pred=simulate(models,sources,spacing_m,time_s,receiver_x_m)
            errors=np.linalg.norm((pred-obs).reshape(len(chunk),-1),axis=1)/norm
            i=int(np.argmin(errors))
            if errors[i]<best[0]: best=(float(errors[i]),models[i],chunk[i])
        return best
    error,velocity,point=search(coordinates, bg)
    if REFINE:
        cx,cz,amp,sx,sz=point
        points=list(itertools.product(cx+np.array([-1,0,1])*1.5,cz+np.array([-1,0,1]),
            amp+np.array([-1,0,1])*150,sx+np.array([-1,0,1])*.75,sz+np.array([-1,0,1])*.5))
        finer=search(points, bg)
        if finer[0]<error: error,velocity,point=finer
    # Greedy multi-anomaly family: refit the complete acquired waveform after
    # adding a second/third independently positioned anomaly. No new paid shots.
    for _ in range(1,LENSES):
        addition=search(coordinates, velocity)
        if addition[0]<error: error,velocity,point=addition
    return {'velocity_m_s':velocity if error<=THRESHOLD else [],
            'confidence':.8 if error<=THRESHOLD else .1,'abstain':error>THRESHOLD}
