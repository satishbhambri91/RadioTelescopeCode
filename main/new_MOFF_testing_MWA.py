import datetime as DT
import numpy as NP
import matplotlib.pyplot as PLT
import matplotlib.colors as PLTC
import scipy.constants as FCNST
import antenna_array as AA
import geometry as GEOM
import sim_observe as SIM
import my_DSP_modules as DSP
import ipdb as PDB

itr = 4

# Antenna initialization

lat = -26.701 # Latitude of MWA in degrees
f0 = 150e6 # Center frequency

antenna_file = '/data3/t_nithyanandan/project_MWA/MWA_128T_antenna_locations_MNRAS_2012_Beardsley_et_al.txt'
ant_info = NP.loadtxt(antenna_file, skiprows=6, comments='#', usecols=(0,1,2,3)) 
ant_info[:,1] -= NP.mean(ant_info[:,1])
ant_info[:,2] -= NP.mean(ant_info[:,2])
ant_info[:,3] -= NP.mean(ant_info[:,3])

# core_ind = NP.logical_and((NP.abs(ant_info[:,1]) < 800.0), (NP.abs(ant_info[:,2]) < 800.0))
core_ind = NP.logical_and((NP.abs(ant_info[:,1]) < 150.0), (NP.abs(ant_info[:,2]) < 150.0))
ant_info = ant_info[core_ind,:]

# ant_info = ant_info[:30,:]

n_antennas = ant_info.shape[0]
nx = 4 # dipoles along x
ny = 4 # dipoles along y
dx = 1.1 # dipole spacing along x
dy = 1.1 # dipole spacing along y

nchan = 16
f_center = f0
channel_width = 40e3
bandwidth = nchan * channel_width
dt = 1/bandwidth

# src_flux = [1.0]
# skypos = NP.asarray([0.0, 0.0]).reshape(-1,2)

# src_flux = [1.0, 1.0]
# skypos = NP.asarray([[0.0, 0.0], [0.1, 0.0]])

src_seed = 50
NP.random.seed(src_seed)
# n_src = NP.random.poisson(lam=5)
n_src = 10
lmrad = NP.random.uniform(low=0.0, high=0.5, size=n_src).reshape(-1,1)
lmang = NP.random.uniform(low=0.0, high=2*NP.pi, size=n_src).reshape(-1,1)
skypos = NP.hstack((lmrad * NP.cos(lmang), lmrad * NP.sin(lmang)))
src_flux = NP.ones(n_src)

# n_src = 4
# src_flux = NP.ones(n_src)
# skypos = 0.25*NP.hstack((NP.cos(2.0*NP.pi*NP.arange(n_src).reshape(-1,1)/n_src),
#                          NP.sin(2.0*NP.pi*NP.arange(n_src).reshape(-1,1)/n_src)))
# src_flux = [1.0, 1.0, 1.0, 1.0] 
# skypos = NP.asarray([[0.25, 0.0], [0.0, -0.25], [-0.25, 0.0], [0.0, 0.25]])
# skypos = NP.asarray([[0.0, 0.0], [0.2, 0.0], [0.0, 0.4], [0.0, -0.5]])

nvect = NP.sqrt(1.0-NP.sum(skypos**2, axis=1)).reshape(-1,1)
skypos = NP.hstack((skypos,nvect))

# ant_locs = NP.asarray([[0.0, 0.0, 0.0],[100.0, 0.0, 0.0],[50.0, 400.0, 0.0]])

ants = []
aar = AA.AntennaArray()
for i in xrange(n_antennas):
    ant = AA.Antenna('{0:0d}'.format(int(ant_info[i,0])), lat, ant_info[i,1:], f0, nsamples=nchan/2)
    ant.f = ant.f0 + DSP.spectax(nchan, dt, shift=True)
    ants += [ant]
    aar = aar + ant

aar.grid()

antpos_info = aar.antenna_positions(sort=True)
Ef_runs = None

# E_timeseries_dict = SIM.monochromatic_E_timeseries(f_center, nchan/2, 2*channel_width,
#                                                 flux_ref=src_flux, skypos=skypos,
#                                                 antpos=antpos_info['positions'])

immax2 = NP.zeros((itr,nchan,2))
for i in xrange(itr):
    # E_timeseries_dict = SIM.monochromatic_E_timeseries(f_center, nchan/2, 2*channel_width,
    #                                                    flux_ref=src_flux, skypos=skypos,
    #                                                    antpos=antpos_info['positions'])
    
    E_timeseries_dict = SIM.stochastic_E_timeseries(f_center, nchan/2, 2*channel_width,
                                                    flux_ref=src_flux, skypos=skypos,
                                                    antpos=antpos_info['positions'],
                                                    tshift=False)

    timestamp = str(DT.datetime.now())
    update_info = {}
    update_info['antennas'] = []
    update_info['antenna_array'] = {}
    update_info['antenna_array']['timestamp'] = timestamp
    for label in aar.antennas:
        adict = {}
        adict['label'] = label
        adict['action'] = 'modify'
        adict['timestamp'] = timestamp
        ind = antpos_info['labels'].index(label)
        adict['t'] = E_timeseries_dict['t']
        adict['gridfunc_freq'] = 'scale'    
        adict['gridmethod'] = 'NN'
        adict['distNN'] = 3.0
        adict['Et'] = {}
        adict['flags'] = {}
        adict['wtsinfo'] = {}
        for pol in ['P1', 'P2']:
            adict['flags'][pol] = False
            adict['Et'][pol] = E_timeseries_dict['Et'][:,ind]
            # adict['wtsinfo'][pol] = [{'orientation':0.0, 'lookup':'/data3/t_nithyanandan/project_MOFF/simulated/MWA/data/lookup/E_illumination_lookup_zenith.txt'}]
            adict['wtsinfo'][pol] = [{'orientation':0.0, 'lookup':'/data3/t_nithyanandan/project_MOFF/simulated/LWA/data/lookup/E_illumination_isotropic_radiators_lookup_zenith.txt'}]
        update_info['antennas'] += [adict]

    aar.update(update_info, parallel=True, verbose=True)
    aar.grid_convolve(pol='P1', method='NN', distNN=0.5*FCNST.c/f0, tol=1.0e-6, maxmatch=1, identical_antennas=True, gridfunc_freq='scale', mapping='weighted', wts_change=False, parallel=True, pp_method='queue')

    imgobj = AA.NewImage(antenna_array=aar, pol='P1')
    imgobj.imagr(weighting='natural', pol='P1')

    # for chan in xrange(imgobj.holograph_P1.shape[2]):
    #     imval = NP.abs(imgobj.holograph_P1[imgobj.mf_P1.shape[0]/2,:,chan])**2 # a horizontal slice 
    #     imval = imval[NP.logical_not(NP.isnan(imval))]
    #     immax2[i,chan,:] = NP.sort(imval)[-2:]

    if i == 0:
        # avg_img = NP.abs(imgobj.holograph_P1)**2
        avg_img = NP.abs(imgobj.img['P1'])**2 - NP.nanmean(NP.abs(imgobj.img['P1'])**2)
    else:
        # avg_img += NP.abs(imgobj.holograph_P1)**2
        avg_img += NP.abs(imgobj.img['P1'])**2 - NP.nanmean(NP.abs(imgobj.img['P1'])**2)

avg_img /= itr
beam = NP.abs(imgobj.beam['P1'])**2 - NP.nanmean(NP.abs(imgobj.beam['P1'])**2)

fig = PLT.figure()
ax = fig.add_subplot(111)
imgplot = ax.imshow(NP.mean(avg_img, axis=2), aspect='equal', origin='lower', extent=(imgobj.gridl.min(), imgobj.gridl.max(), imgobj.gridm.min(), imgobj.gridm.max()))
posplot, = ax.plot(skypos[:,0], skypos[:,1], 'o', mfc='none', mec='black', mew=1, ms=8)
ax.set_xlim(imgobj.gridl.min(), imgobj.gridl.max())
ax.set_ylim(imgobj.gridm.min(), imgobj.gridm.max())
PLT.savefig('/data3/t_nithyanandan/project_MOFF/simulated/MWA/figures/MOFF_image_random_source_positions_{0:0d}_iterations.png'.format(itr), bbox_inches=0)

fig = PLT.figure()
ax = fig.add_subplot(111)
imgplot = ax.imshow(NP.mean(beam, axis=2), aspect='equal', origin='lower', extent=(imgobj.gridl.min(), imgobj.gridl.max(), imgobj.gridm.min(), imgobj.gridm.max()))
ax.set_xlim(imgobj.gridl.min(), imgobj.gridl.max())  
ax.set_ylim(imgobj.gridm.min(), imgobj.gridm.max())
PLT.savefig('/data3/t_nithyanandan/project_MOFF/simulated/MWA/figures/MOFF_psf_square_illumination.png'.format(itr), bbox_inches=0)



