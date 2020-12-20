from dataclasses import dataclass
import TAUpost.wake.helpers.wake_stats as ws
from wake_config import WakeCaseParams
import TAUpost.pyTecIO.tecreader as tecreader
import os
import numpy as np
###############################################################################
# Some data classes, never used
class DataField():
    def __init__(self):
        dims = 2
        struct_data = False

class Coordinates:
    def __init__(self, x=None,y=None,z=None):
        self.x = x
        self.y = y
        self.z = z

@dataclass(init=False)
class FieldSeries():
    """NetCDF file

    Loads the input file with the NetCFD (.nc) format and
    initialize the variables.

    """

    u: np.ndarray
    v: np.ndarray
    w: np.ndarray

    '''
    def __init__(self, time=0, x=None,y=None, z=None,u=None,v=None, w=None, struct_data=False, planar=True):
        #vel = VelocityField(self)
        #DataField.__init__(self)
        #self.coords = {}
        self.vel = {}
        self.set_velocities(u,v,w)

        self.planar = planar
                #self.sizex=cols
        #self.sizey=rows

        #print(str(cols) + ' cols by ' + str(rows) + ' rows')
        self.mean_u, self.mean_v, self.mean_w = compute_means(u,v,w)
        self.gradients = {}
        self.set_velocities(u,v,w)
    '''
    def set_velocities(self,u,v,w):
        self.u = u
        self.v = v
        self.w = w

    def set_coords(self,x,y,z):
        self.x = x
        self.y = y
        self.z = z

    def computeGradients(self):
        dudy,dudx=np.gradient(self.vx,-self.dy/1000,self.dx/1000)
        dvdy,dvdx=np.gradient(self.vy,-self.dy/1000,self.dx/1000)
        self.gradients['dudy']=dudy
        self.gradients['dudx']=dudx
        self.gradients['dvdy']=dvdy
        self.gradients['dvdx']=dvdx
        # TODO and so on

        #skip = 0
        #self.u  = np.array(u).reshape(self.sizey,self.sizex)
        #self.v  = np.array(w).reshape(self.sizey,self.sizex)
        #self.u = self.u[:,skip:]
        #self.v = self.v[:,skip:]

@dataclass
class ReynoldsStress():
    uu: np.ndarray = None
    vv: np.ndarray = None
    ww: np.ndarray = None
    uv: np.ndarray = None
    uw: np.ndarray = None
    vw: np.ndarray = None
    kt: np.ndarray = None

    def set_unnamed(self, initial_data):
        print(initial_data)
        for key in initial_data:
            setattr(self, key, initial_data[key])

    # https://stackoverflow.com/questions/2466191/set-attributes-from-dictionary-in-python
    def set_values(self, *initial_data, **kwargs):
        print('setting values')
        print(initial_data)
        for dictionary in initial_data:
            print(initial_data)
            for key in dictionary:
                print('setting ' + str(key))
                setattr(self, key, dictionary[key])
        for key in kwargs:
            setattr(self, key, kwargs[key])



@dataclass
class AnisotropyData():
    uu: np.ndarray = None
    vv: np.ndarray = None
    ww: np.ndarray = None
    uv: np.ndarray = None
    uw: np.ndarray = None
    vw: np.ndarray = None
    def set_values(a_uu, a_vv, a_ww, a_uv, a_uw, a_vw):
        self.uu = a_uu
        self.vv = a_vv
        self.ww = a_ww
        self.uv = a_uv
        self.uw = a_uw
        self.vw = a_vw



@dataclass
class WakeField():
    vel: FieldSeries = None
    vel_prime: FieldSeries = None
    dataset = None # Tecplot dataset
    rstresses: dict = None
    atensor: dict = None
    cs: str = 'AC'
    coords: Coordinates = None
    param: WakeCaseParams = None

    #def set_coords(self, x, y, z):
    #    self.coords = Coordinates(x=x, y=y, z=z)
    def set_coords(self,x,y,z):
        self.x = x
        self.y = y
        self.z = z

    def rotate_CS(self, alpha, CSname):
        ws.rotate_dataset(self.dataset, self.param.x_PMR, self.param.z_PMR, self.param.aoa)
        x_WT, z_WT = ws.transform_wake_coords(self.vel.x,self.vel.z, self.param.x_PMR, self.param.z_PMR, self.param.aoa)
        u_WT, w_WT = ws.rotate_velocities(self.vel.u, self.vel.v, self.vel.w, self.param.x_PMR, self.param.z_PMR, self.param.aoa)
        self.vel.u = u_WT
        self.vel.w = w_WT
        self.cs = CSname


        self.set_coords(x_WT, self.y, z_WT)

    def compute_rstresses(self, do_save = False):
        #uu,vv,ww,uv,uw,vw = ws.calc_rstresses(u,v,w)
        #self.rstresses = ReynoldsStress
        #self.rstresses.set_values()
        self.rstresses = ws.calc_rstresses(self.vel.u, self.vel.v, self.vel.w, return_dict=True)
        self.rstresses['kt'] = 0.5* (self.rstresses['uu'] + self.rstresses['vv'] + self.rstresses['ww'])

        #print('d: ' + str(d))
        #self.rstresses.set_unnamed(d)
        #print(type(self.rstresses))
        #print(type(self.rstresses['uu']))
        #self.rstresses.uu,vv,ww,uv,uw,vw = ws.calc_rstresses(u_WT,v,w_WT)
        if do_save:
            self.save_rstresses(self.rstresses, res_path = self.param.res_path, file_prefix = self.param.case_name+'_'+ self.param.plane_name)

    def save_rstresses(self, rstress, res_path = None, file_prefix = None):
        if res_path is None:
            res_path = self.param.res_path
        if file_prefix is None:
            file_prefix = self.param.case_name+'_' + self.param.plane_name
        # Save the results

        try:
            os.makedirs(res_path, mode = 0o777, exist_ok = True)
            print("Directory '%s' created successfully" %res_path)
        except:
            print("Directory '%s' can not be created"%res_path)

        save_var= {'uu': rstress['uu'], 'vv': rstress['vv'], 'ww': rstress['ww'], \
                'uv': rstress['uv'], 'uw': rstress['uw'], 'vw': rstress['vw'], 'kt': rstress['kt']}

        filename = os.path.join(res_path, file_prefix + '_rstresses.plt')
        tecreader.save_plt(save_var, self.dataset, filename, addvars = True, removevars = True)



    def compute_fluctuations(self):
        self.vel.uprime, self.vel.vprime, self.vel.wprime = ws.compute_fluctuations(self.vel.u, self.vel.v, self.vel.w)



    def compute_means(self):

        mean_u = np.mean(u, axis=-1)
        mean_v = np.mean(v, axis=-1)
        mean_w = np.mean(w, axis=-1)

    def compute_anisotropy(self, do_save = False):
        self.atensor = AnisotropyData
        if self.rstresses is None:

            self.compute_rstresses()
            self.rstresses['kt'] = 0.5* (self.rstresses['uu'] + self.rstresses['vv'] + self.rstresses['ww'])
        print('coords :' +str(self.coords))
        # Compute the anisotropy tensor
        a_uu, a_vv, a_ww, a_uv, a_uw, a_vw = ws.compute_atensor(self.rstresses['uu'], \
        self.rstresses['vv'], \
        self.rstresses['ww'], \
        self.rstresses['uv'], \
        self.rstresses['uw'], \
        self.rstresses['vw'], \
        self.rstresses['kt'])
        # Compute second and third invariants of the anisotropy tensor
        self.atensor = {'uu': a_uu, 'vv': a_vv, 'ww': a_ww, 'uv': a_uv, 'uw': a_uw, 'vw': a_vw}

        invar2, invar3, ev = ws.compute_anisotropy_invariants(a_uu, a_vv, a_ww, a_uv, a_uw, a_vw)
        # Compute barycentric coordinates
        C, xb, yb = ws.compute_anisotropy_barycentric(ev)

        if do_save:
            self.save_anisotropy(self.atensor, ev, C, res_path = self.param.res_path, file_prefix = self.param.case_name+'_'+ self.param.plane_name)

    def save_plt():
        pass


    def data_to_dict(**kwargs):
        out = {}
        for key, value in kwargs.items():
            out[key] = value
        return out

    def transform(self):
        ws.rotate_dataset(self.dataset, param.x_PMR, param.z_PMR, param.aoa)
        x_WT, z_WT = ws.transform_wake_coords(vel.x,vel.z, param.x_PMR, param.z_PMR, param.aoa)
        u_WT, w_WT = ws.rotate_velocities(vel.u, vel.v, vel.w, param.x_PMR, param.z_PMR, param.aoa)


    def save_anisotropy(self, atensor, ev, C, res_path = None, file_prefix = None):
        if res_path is None:
            res_path = self.param.res_path
        if file_prefix is None:
            file_prefix = self.param.case_name+'_' + self.param.plane_name
        # Save the results

        try:
            os.makedirs(res_path, mode = 0o777, exist_ok = True)
            print("Directory '%s' created successfully" %res_path)
        except:
            print("Directory '%s' can not be created"%res_path)

        save_var= {'a_uu': atensor['uu'], 'a_vv': atensor['vv'], 'a_ww': atensor['ww'], \
                'a_uv': atensor['uv'], 'a_uw': atensor['uw'], 'a_vw': atensor['vw']}

        filename = os.path.join(res_path, file_prefix + '_anisotropy_tensor.plt')
        print(filename)
        tecreader.save_plt(save_var, self.dataset, filename, addvars = True, removevars = True)

        save_var= {'ev1': ev[0,:], 'ev2': ev[1,:], 'ev3': ev[2,:]}

        filename = os.path.join(res_path, file_prefix + '_anisotropy_eigenvalues.plt')
        tecreader.save_plt(save_var, self.dataset, filename, addvars = True, removevars = True)

        save_var= {'C1': C[0,:], 'C2': C[1,:], 'C3': C[2,:]}

        filename = os.path.join(res_path, file_prefix + '_anisotropy_components.plt')
        tecreader.save_plt(save_var, self.dataset, filename, addvars = True, removevars = True)

    def compute_independent_samples(self):
        # Compute the autocorrelation function at each point
        uprime, vprime, wprime = ws.compute_fluctuations()
        acf_u = wt.compute_field_acf(uprime, 300)
        acf_w = wt.compute_field_acf(wprime, 300)

        # Obtain the number of independent samples based on the ACF
        ind_u = wt.compute_field_acf_index(acf_u)
        ind_w = wt.compute_field_acf_index(acf_w)



class VelocityField(DataField):
    def __init__(self, x=None,z=None,v=None,u=None,w=None):
        DataField.__init__(self)
        self.coords = {}
        self.vel = {}
        self.set_velocities(u,v,w)

    def set_velocities(self,u,v,w):
        self.vel['u'] = u
        self.vel['v'] = v
        self.vel['w'] = w
