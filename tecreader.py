import tecplot as tp
import numpy as np
import sys, os, fnmatch
from memory_profiler import profile
import time
from functools import wraps
import multiprocessing as mp

'''
This module facilitates loading of Tecplot-formatted binary file series, usually from Tau results.
The approach is thus:
- obtain a file list from the path in question using get_sorted_filelist()
- set start_i and end_i in order to get a sublist, optionally you can use get_cleaned_filelist()
- use either
	in_data = tecreader.read_series_parallel([plt_path + s for s in filelist], zone_no, varnames, n_workers)
or

	in_data = tecreader.read_series(plt_path, zone_no, varnames)
to obtain a numpy array of shape (n_points, n_timesteps, n_variables)

'''

def fn_timer(function):
    @wraps(function)
    def function_timer(*args, **kwargs):
        t0 = time.time()
        result = function(*args, **kwargs)
        t1 = time.time()
        print ("Total time running %s: %s seconds" %
               (function.func_name, str(t1-t0))
               )
        return result
    return function_timer


def read_series(source_path, zone, varnames):
    if isinstance(source_path, str):
        filelist, num_files= get_sorted_filelist(source_path, 'plt')
    else:
        filelist = source_path
        num_files = len(filelist)
    print(num_files)
    print('reading zones: ' + str(zone))
    start_time = time.time()
    f_r = []
    for i in range(len(filelist)):
        _,_,_, data_i, dataset = load_tec_file(source_path + filelist[i], szplt=False, verbose=False, varnames=varnames, load_zones=zone, coords=False, deletezones=False, replace=True)
        f_r.append(data_i)

    f_r = np.asarray(f_r)
    print('finished reading after ' + str(time.time()-start_time) + ' s')
    print('shape of result before transposition: ' + str(f_r.shape))
    return f_r


def parallel_load_wrapper(input_arg):
    (filename, zone, varnames) = input_arg
    _,_,_,data_i,dataset = load_tec_file(filename, szplt=False, verbose=False, varnames=varnames, load_zones=zone, coords=False, deletezones=False, replace=True)
    print data_i.shape
    return data_i

def read_series_parallel(source_path, zone, varnames, workers):
    """ Reads a file list using multiple threads
    Parameters
    ----------
    source_path : str or list
        Path containing the files or list of files
    zone : list of str or int
        Zones to load
    varnames : list of str
        Variables to load
    workers : int
        the stride

    Raises
    ------

    Description
    -----------

    Read a time series of files in binary Tecplot format using pytecplot, tested with the PyTecplot version supplied with 2017R3.
    This can only work if there is a connection to a Tecplot licence server!
    x, y, z are always read. varname is required and should contain single quotes e.g. 'cp'
    This function does not care whether data is structured or not
    """

    nProc = workers
    pool = mp.Pool(processes=nProc)
    if isinstance(source_path, str):
        filelist, num_files= get_sorted_filelist(source_path, 'plt')
    else:
        filelist = source_path
        num_files = len(filelist)
    #filelist = filelist[0:31]
    #num_files = len(filelist)
    print(num_files)
    print('reading zones: ' + str(zone))
    start_time = time.time()
    #print source_path
    args = ((filelist[i], zone, varnames) for i in range(len(filelist)))
    results = pool.map_async(parallel_load_wrapper, args)
    f_r = results.get()
    f_r = np.asarray(f_r)

    pool.close()
    pool.join()

    print('finished reading after ' + str(time.time()-start_time) + ' s')
    print('shape of result before transposition: ' + str(f_r.shape))
    if f_r.ndim < 3:
        f_r = f_r[:,:,None]
    return np.transpose(f_r, (1,0,2))



'''

The actual data are found at the intersection of a Zone and Variable and the resulting object is an Array. The data array can be obtained using either path:

>>>

>>> # These two lines obtain the same object "x"
>>> x = dataset.zone('My Zone').values('X')
>>> x = dataset.variable('X').values('My Zone')


'''

def get_sorted_filelist(source_path, extension, sortkey='i', stride=10):
    print('looking for data in '  + source_path + ' using pattern *.' + extension)
    if os.path.isdir(source_path): # folder of files
        filelist = fnmatch.filter(os.listdir(source_path), '*.' + extension)
        if sortkey == 'i':
            filelist = sorted(filelist, key = get_i)
        else:
            filelist = sorted(filelist, key = get_domain)
        num_files = len(filelist)
    else: # single file
        filelist = list(source_path)
        num_files = 1
    newlist= []
    for file in filelist:
        if (get_i(file) % 10) == 0:
            newlist.append(file)
    num_files = len(newlist)

    return newlist, num_files

def get_i(s):
    temp= s.split('i=')[1]
    i = temp.split('.plt')[0]
    i = i.split('_t=')[0]
    return int(i)

def get_t(s):
    temp= s.split('t=')[1]
    t = temp.split('e')[0]
    return int(t)

def get_domain(s):
    temp= s.split('domain_')[1]
    dom = temp.split('.plt')[0]
    return int(dom)




def get_zones(dataset, keepzones='byname', zonenames=['hexa']):
    '''
    select zones by number, name, dimension or some other aspect
    '''
    if keepzones =='byname':
        # problem#
        pass
        #[Z for Z in dataset.zones() if 'Wing' in Z.name]
        #found = any(word in item for item in wordlist)
        delzones
    if keepzones == '3D':
        zones2D = [Z for Z in dataset.zones() if Z.rank < 3]
        print(str(zones2D))
        dataset.delete_zones(zones2D)
        print('deleted 2D zones, what remains is')
        print('number of zones: ' + str(dataset.num_zones))
        for zone in coords_data.zones():
            print(zone.name)
    elif keepzones == '2D':
        zones2D = [Z for Z in dataset.zones() if Z.rank > 2]
        print(str(zones2D))
        dataset.delete_zones(zones2D)
        print('deleted 3D zones, what remains is')
        print('number of zones: ' + str(dataset.num_zones))
        for zone in dataset.zones():
            print(zone.name)

#@profile(precision=4)
@fn_timer
def read_ungathered(source_path, load_zones=None, szplt=False, varnames=None, shape=None, verbose=False):
    if not os.path.isdir(source_path):
        raise IOError(str(source_path) + ' does not exist.')

    # special case: if no varnames are given, we assume that we want velocities
    if varnames is None:
        varnames=['X', 'Y', 'Z', 'x_velocity', 'y_velocity', 'z_velocity']
    if szplt:
        filelist, num_files= get_sorted_filelist(source_path, 'szplt')
    else:
        filelist, num_files= get_sorted_filelist(source_path, 'plt', sortkey='domain')

    print('found ' + str(num_files) + ' files total in the folder')

    s=filelist[0]

    readoption = tp.constant.ReadDataOption.Append

    data = np.empty((0,6))
    for file in range(len(filelist)):
        s = filelist[file]
        #dataset = tp.data.load_tecplot(source_path+s, zones=load_zones, read_data_option=readoption)
        try:
            _,_,_,data_i, _ = load_tec_file(source_path + s, szplt=False, varnames=varnames, load_zones=load_zones, coords=False, verbose=False, deletezones=False, replace=True)
            data = np.vstack((data, data_i))
        except NameError:
            print 'requested zone not found, no problem'

    print data.shape
    print('velocity snapshot shape: ' + str(data.shape) + ', size ' + str(size_MB(data)) + ' MB')

def get_cleaned_filelist(filelist, start_i, end_i):
    startindex = None
    endindex = None
    for item in filelist:
        if get_i(item) == start_i:
            startindex = filelist.index(item)
        elif get_i(item) == end_i:
            endindex = filelist.index(item)
    if startindex is None or endindex is None:
        return filelist
    else:
        return filelist[startindex:endindex]

def cleanlist(filelist, skip=None, start_i=None, end_i=None, num_i=None, di=10):
    ###########################################################################
    # sort out the various options for starting, skipping and ending
    # where to start? is start_i or skip given? (these are mutually exclusive)
    if skip is None:
        skip = 0

    if start_i is None:
        start_i = get_i(s)
    else:
        start_i = start_i + skip
    print('starting at I ' + str(start_i))

    if num_i is None and end_i is None:
        maxcount = num_files - (skip // di)
        print('going to the last file')
        end_i = get_i(filelist[-1])
    elif num_i is not None and end_i is None:
        end_i = start_i + (num_i-1) * di
        print('ending at I ' + str(end_i))
    elif num_i is None and end_i is not None:
        maxcount = (end_i - start_i + di) // di
        print('ending at I ' + str(end_i))
        num_i = (end_i - start_i + di) // di
    else:
        sys.exit('num_i and end cannot be both specified at the same time')
    maxcount = (end_i - start_i + di) // di
    num_i = maxcount

    return start_i, end_i, num_i


#@profile(precision=4)
def read_tec_bin_series(source_path, load_zones=None, szplt=False, varnames=None, shape=None, skip=None, start_i=None, end=None, num_i=None, di=10, verbose=False):
    """ Loads a time series of binary Tecplot data using the PyTecplot API.
    Parameters
    ----------
    source_path : str
        Path containing the data.
    load_zones : list of str or int, default None
        Lists the zones to be loaded
    szplt : bool
        sets whether data is in old Tecplot PLT binary format or in the new SZPLT
    varnames : list of str, default None
        Variables to load. If None then all are kept
    skip : int
        number of files to skip at the beginning. Mutually exclusive with start_i
    start_i : int
        First file to load. Mutually exclusive with skip.
    end : int
        Last file to load. Mutually exclusive with num_i
    num_i : int
        number of files to load. Mutually exclusive with Append
    di :
        the stride
    verbose :
        verbosity of console output

    Raises
    ------
    IOError
        If path does not exist.

    Description
    -----------

    Read a time series of files in binary Tecplot format using pytecplot, tested with the PyTecplot version supplied with 2017R3.
    This can only work if there is a connection to a Tecplot licence server!
    x, y, z are always read. varname is required and should contain single quotes e.g. 'cp'
    This function does not care whether data is structured or not
    """
    if not os.path.isdir(source_path):
        raise IOError(str(source_path) + ' does not exist.')

    # special case: if no varnames are given, we assume that we want velocities
    if varnames is None:
        varnames=['x_velocity', 'y_velocity', 'z_velocity']
    if szplt:
        filelist, num_files= get_sorted_filelist(source_path, 'szplt')
    else:
        filelist, num_files= get_sorted_filelist(source_path, 'plt')

    print('found ' + str(num_files) + ' files total in the folder')

    s=filelist[0]

    ###########################################################################
    # sort out the various options for starting, skipping and ending
    # where to start? is start_i or skip given? (these are mutually exclusive)
    if skip is None:
        skip = 0

    if start_i is None:
        start_i = get_i(s)
    else:
        start_i = start_i + skip
    print('starting at I ' + str(start_i))

    if num_i is None and end is None:
        maxcount = num_files - (skip // di)
        print('going to the last file')
        end = get_i(filelist[-1])
    elif num_i is not None and end is None:
        end = start_i + (num_i-1) * di
        print('ending at I ' + str(end))
    elif num_i is None and end is not None:
        maxcount = (end - start_i + di) // di
        print('ending at I ' + str(end))
        num_i = (end - start_i + di) // di
    else:
        sys.exit('num_i and end cannot be both specified at the same time')
    maxcount = (end - start_i + di) // di
    num_i = maxcount

    start_i, end_i, num_i = cleanlist(filelist, skip=skip, start_i=start_i, end_i=end, num_i=num_i, di=di)

    print('reading ' + str(num_i) + ' files')

    count=0
    print('num_files: ' + str(num_i))


    ###########################################################################
    data = dict()
    for file in range(len(filelist)):
        s = filelist[file]
        i = get_i(s)

        # skip before starting I
        if (i < start_i):
            continue
        verbose = True
        if verbose:
            print('processing i=' + str(i))
        #verbose = False
        # do verbosity only on first file
        print('calling load function...\n')
        if count == 0:
            verbose = verbose
            print('acquiring dataset for later output...')

            # the first frame contains the data set of the first file, usually in order to retain the data structure for future handling
            page = tp.active_page()
            frame1 = page.active_frame()
            if szplt:
                coords_data = tp.data.load_tecplot_szl(source_path + s)
            else:
                coords_data = tp.data.load_tecplot(source_path + s, zones=load_zones, variables = [0,1,2])

            frame2 = page.add_frame()
            frame2.activate()
            x,y,z,data_i, dataset = load_tec_file(source_path + s, szplt=szplt, varnames=varnames, load_zones=load_zones,coords=True, verbose=verbose, deletezones=False, replace=False)
        else:
            verbose = False
            _,_,_,data_i, _ = load_tec_file(source_path + s, szplt=szplt, varnames=varnames, load_zones=load_zones, coords=False, verbose=verbose, deletezones=False)
        
        print('shape of data array after file count '+str(count)+': ' + str(data_i.shape))


        # initialize array for entire dataset
        if count < 1:
            print(str(x))
            num_points = len(data_i)
            print('num_points: ' + str(num_points))

            for var in range(len(varnames)):
                print('creating dict field for variable ' + varnames[var] + ' to hold all ' + str(num_points) + ' points and ' + str(num_i) + ' snapshots' )
                data[varnames[var]] = np.zeros([num_points, num_i])
            print('data is dict with keys ' + str(data.keys()))
            for key in data.keys():
                print('shape of ' + str(key) + ': ' + str(data[key].shape))


        else:
            pass
                
        # assign the data just read to the overall dataset
        for var in range(len(varnames)):
            #print(str(var))
            #print('data_i: ' + str(type(data_i)))
            #print('data_i: ' + str(data_i.shape))
            data[varnames[var]][:,count] = data_i[:,var] # for when data_i is not a dict but a simple numpy array

        count += 1

        if get_i(s) >= end:
            break
    print('finished reader loop')


    if shape is not None:
        for var in range(len(varnames)):
            data[varnames[var]] = data[varnames[var]].reshape(rows,cols,num_files)

    # reactivate the frame containing the very first data set
    # delete the frame containing the last data set (possibly unnecessary, just some cleanup)
    frame1.activate()
    page.delete_frame(frame2)

    return x, y, z, data, frame1.dataset

def tec_data_info(dataset):
    print('number of variables: ' + str(dataset.num_variables))
    print('number of zones: ' + str(dataset.num_zones))
    print('title of dataset: ' + str(dataset.title))
    for variable in dataset.variables():
        print(variable.name)
        #array = variable.values('hexa')
    for zone in dataset.zones():
        print(zone.name)
        print(zone)
        #x_array = zone.variable('X') # this does not work

def size_MB(array):
    return array.nbytes / (1024*1024)

def get_coordinates(dataset):
    zone_no = 0
    print('number of zones: ' + str(dataset.num_zones))

    for zone in dataset.zones():
        array = zone.values('X')
        b1 = np.array(array[:]).T
        
        array = zone.values('Y')
        b2 = np.array(array[:]).T
        
        array = zone.values('Z')
        b3 = np.array(array[:]).T
        
        if zone_no == 0:
            x = b1
            y = b2
            z = b3
        else:
            x = np.hstack((b1, x))
            y = np.hstack((b2, y))
            z = np.hstack((b3, z))
        print(str(zone_no))
        zone_no += 1

    print(str(x))
    print(str(x.shape))
    
    print(str(y.shape))
    print(str(z.shape))
    #sys.exit(0)
    return x,y,z

    

def load_tec_file(filename, szplt=False, varnames=None, load_zones=[0,1], coords=True, verbose=True, deletezones=True, replace=True):
    '''
    Read a Tecplot binary file using pytecplot, tested with version 0.9 (included in Tecplot 2017 R3)
    
    This reads a data file and concatenates the values of all zones to a column.
    If more than one variable is requested then the variables are added as further columns.
    The returned dataset is a numpy array of dimensions (n_points, n_variables) where
    n_points is the total number of points in the zones
    
    The zones are deleted at the end of the file. The rationale for this is that Tecplot
    keeps the dataset persisent, i.e. when this function is called repeatedly then the new
    data is simply added. The delete_zones function deletes all but one zone.
    TODO: delete_zones may be better called somewhere else
    '''
    """ Loads a time series of binary Tecplot data using the PyTecplot API.
    Checks if a binary file (i.e. HDF5) exists and reads the velocity data accordingly.
    If binary does not exist, the ASCII time series is read one by one
    Parameters
    ----------
    source_path : str
        Path containint the data.
    coords : bool
        if True then coordinate variables x,y,z are returned
        Variables to load. If None then all are kept
    skip : tuple or None
        rows and columns of structured data set
    start_i : str or None
        The type string of the data, or ``None`` to deduce
        automatically.
    end : str or None
        The options to use when writing.
    num_i :

    """
    if varnames is None:
        varnames=['x_velocity', 'y_velocity', 'z_velocity']
    if verbose:
        print('loading tecplot file '+filename + ' and looking for variables ' + str(varnames))
    if replace:
        readoption = tp.constant.ReadDataOption.Replace
    else:
        readoption = tp.constant.ReadDataOption.Append

    # load the actual data. in case of SZPLT all zones are loaded
    if szplt:
        dataset = tp.data.load_tecplot_szl(filename, read_data_option=readoption)
        get_zones(dataset, zones)
    else:
        if load_zones is not None:
            if not all(isinstance(x, (int)) for x in load_zones):
                raise ValueError
            dataset = tp.data.load_tecplot(filename, zones=load_zones, read_data_option=readoption)
        else:
            dataset = tp.data.load_tecplot(filename, read_data_option=readoption)
    if verbose:
        tec_data_info(dataset)
        print 'done with dataset info'
    # apparently tecplot appends to its dataset all the time, insteady of opening a new one
    # basically it adds the zones of each time step to the dataset, ending up with a lot of zones after a while
    # ---> use delete_zones?
    #dataset.delete_zones(dataset.zone('Zone 2'))
    # or
    #dataset.delete_zones( ([dataset.zone for z in dataset.zones()] )) or something
    # or simply dataset.delete_zones(range(8)) to delete the first 8

        
    #############################################
    # this accumulates all points of a single variable into a single numpy array by stacking all zones on top of each other
    # this is very useful.
    if coords is True:
        x,y,z = get_coordinates(dataset)
        if verbose:
            print('obtained coordinates, length: ' + str(len(x)))
    else:
        x=None
        y=None
        z=None

    count = 0
    zone_no = 0
    #n_vars = len(varnames)


    # we need a away to build a list of relevant zones, since we cannot delete e.g. the very first zone
    #load_zones = ['flunten', 'floben']
    if load_zones is not None:
        if verbose:
            print 'zones to load: ' + str(load_zones)
        if any(isinstance(x, (str)) for x in load_zones):
            # load_zones is a list of strings
            zonelist = [Z for Z in dataset.zones() if Z.name in load_zones]
        elif any(isinstance(x, (int)) for x in load_zones):
            pass
            zonelist = [dataset.zone(ind) for ind in load_zones]
    else:
        zonelist = [Z for Z in dataset.zones()]

    #nz = dataset.num_zones
    nz = len(zonelist)
    if verbose:
        print('number of zones: ' + str(nz))

    if nz < 1:
        raise NameError
    # read zones and do what needs to be done (convert arrays to numpy) 
#    for zone in dataset.zones():
    for zone in zonelist:
        if verbose:
            print('zone: ' + str(zone.name) + ', rank: ' + str(zone.rank))

        # each variable gets a column
        for var in range(len(varnames)):
            array = zone.values(varnames[var])
            if var == 0:
                b = np.array(array[:])
            else:
                b = np.vstack((b, np.array(array[:])))
            #print('shape of current array: ' + str(b.shape))
        b = b.T
        if zone_no == 0:
            data = b
        else:
            if verbose:
                print('before stacking data shape: ' + str(data.shape))
            data = np.vstack((b, data))
            if verbose:
                print('after stacking: ' + str(data.shape))
        count = count + 1
        zone_no = zone_no + 1
    if verbose:        
        print('velocity snapshot shape: ' + str(data.shape) + ', size ' + str(size_MB(data)) + ' MB')
    if deletezones:
        try:
            for zone in dataset.zones():
                dataset.delete_zones(zone)
                #dataset.delete_zones(dataset.zones())
        except (tp.exception.TecplotLogicError):
            print('normal exception when deleting, no worries')    
    if verbose:
        print('\nload function done \n\n')
        print data.shape
    return x,y,z,data, dataset



def main():
    #in_file = '/home/andreas/CRM/CFD/M025_ESWIRP/AoA18/IDDES_dt200_LD2/sol/CRM_v38_WT_SAO_a18_DES.vol1_vel_i=25052_t=1.546142500e+00.plt'
    #in_file = '/lustre/nec/ws2/ws/iagwaldm-OAT15_06/AZDES-SSG/AZDES-SSG_dt2e5_turbRoe_SGDH_Lc0014/sol/plt/hifreq/OAT15A_URANS-SSG.pval.unsteady_i=13500_t=2.700000000e-01.plt'
    #load_tec_file(
    source_path = '/lustre/nec/ws2/ws/iagwaldm-OAT15_06/AZDES-SSG/AZDES-SSG_dt2e5_turbRoe_SGDH_Lc0014/sol/plt/hifreq/szplt/'
    shape = None
    skip = None
    start_i = 13510
    di = 10
    verbose = True
    num_i = 50
    x,y,z, data = read_tec_bin_series(source_path, szplt=True, shape=shape, skip=skip, start_i=start_i, end=None, num_i=num_i, di=di, verbose=verbose)
    #print(data['"z_velocity"'][:,0])
    #print(data['"z_velocity"'][:,-1])
    #print(data['"z_velocity"'].shape)
    for key in data.keys():
            print('size of ' + str(key) + ' matrix: ' + str(size_MB(data[key])) + ' MB')


    ######################################################################
    # DMD    
    import dmd_v2
    import cylinder_plotters as cyl_plot
    import matplotlib.pyplot as plt
    plt.switch_backend('agg')
    img_path = './'

    dt = 2e-4
    phi, eigvals, lambda_dmd, SV, b, Vand = dmd_v2.dmd(M=data['z_velocity'], dt=dt, order=False, scale_modes=False, verbose=True)
    freq=np.imag(lambda_dmd)/(2.0*np.pi)
    
    #n_vars = len(varnames)
    print('type of GR: ' + str(type(b['GR'][0])))
    print('type of JO: ' + str(type(b['JO'][0])))
    print('type of BR: ' + str(type(b['BR'][0])))

    title = 'DMD_v2_OAT15A'
    write_DMD_results('./', title, eigvals, np.real(lambda_dmd), SV, freq, b)

    #write_DMD_mode_ASCII('a.dat', \
    #                     x, y, modes[:,:,mode_no], modes.shape, 'uuu', ['uv'])

    #print eigvals
    fig, ax = cyl_plot.plot_eigvals_re_im_circle(np.real(eigvals), np.imag(eigvals))
    plt.savefig(img_path+'eigvals.png', dpi=600)
    plt.close()
    
    fig, ax = plt.subplots(1,1)
    plt.scatter(freq, np.real(lambda_dmd),s=2)
    print('maximum relambda: ' + str(np.max(np.real(lambda_dmd))))
    plt.ylim(-3e-9,3e-9)

    plt.savefig(img_path+'lambdas.png', dpi=600)
    plt.close()
    
    fig, ax = plt.subplots(1,1)
    plt.scatter(freq, b['GR'],s=2)
    plt.xlim(0,np.max(freq))
    plt.savefig(img_path+'freq_amp_GR.png', dpi=600)
    plt.close()   
    
    
    #for keys, values in data.iteritems():
    #    print('data shape: ' + str(values.shape) + ', size ' + str(size_MB(values)) + ' MB')




if __name__ == "__main__":
    main()
