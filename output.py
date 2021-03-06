import glob
import h5py
import numpy as np
import os


# define map to the HDF5 datasets
dset_aliases = {"t" : "   time",
                "x1": "i coord",
                "x2": "j coord",
                "x3": "k coord",
                "dV1":"ivolume",
                "dV2":"jvolume",
                "dV3":"kvolume",
                "v1": " i velocity", 
                "v2": " j velocity", 
                "v3": " k velocity", 
                "B1": "i mag field", 
                "B2": "j mag field", 
                "B3": "k mag field", 
                "e":  " gas energy",
                "d":  "gas density",
                "T":  "temperature",
                "cs2":"soundspeed2",
                "gp" :"g potential",
                "A":  "aspec",
                "Z":  "zspec",
                "X":  "abun"}


class ZeusFile(h5py.File):

    def get_dset(self, name):
        return self[dset_aliases[name]][:]

class ZeusData:
    
    def __init__(self, filename):
        with ZeusFile(filename) as zf:
            for alias in dset_aliases.keys():
                try:
                    setattr(self, alias, np.squeeze(zf.get_dset(alias)))
                except:
                    setattr(self, alias, None)

    def __enter__(self):
        return self

    def __exit__(self, etype,evalue, tb):
        pass

class Error(Exception):
    pass

class ComparisonError(Error):

   def __init__(self, var, value1, value2):
       self.var = var
       self.value1 = value1
       self.value2 = value2

class DifferenceError(Error):

   def __init__(self, var, rerr, aerr, locs, rtol):
       self.var = var
       self.rerr = rerr
       self.aerr = aerr
       self.locs = locs
       self.rtol = rtol

   def showall(self, iskip = (), jskip = (), kskip = () ):
       diff_fmt = "    Does not match at ({:4d},{:4d},{:4d})  |  diff = ({:8.2E}, {:8.2E})"
       for (k,j,i) in  zip(*self.locs):
           if not ((i in iskip) or (j in jskip) or (k in kskip)):
               if self.rerr[k,j,i] > self.rtol: 
                   print(diff_fmt.format(i,j,k,self.rerr[k,j,i],self.aerr[k,j,i]))

def assert_near_equality(a,b, rtol = 1e-15, atol = 0):

    c1 = np.allclose(a,b,rtol = rtol, atol = atol)
    c2 = np.allclose(b,a,rtol = rtol, atol = atol)
    
    if not (c1 and c2):
        rerr  = np.abs(a-b) / np.abs(a+b) 
        aerr  = np.abs(a-b)
        locs = aerr.nonzero()
        raise DifferenceError(None, rerr, aerr, locs, rtol)
        
    return

def assert_equality(a,b):

    if not np.array_equal(a,b):
        rerr  = np.abs(a-b) / np.abs(a+b) 
        aerr  = np.abs(a-b)
        locs = aerr.nonzero()
        raise DifferenceError(None, rerr, aerr, locs, rtol)
        
    return
                    
def compare_two(file1, file2, rtol = 1e8, 
                unforgiving = True, verbose = True, force = False):

    print("Comparing {} with {}".format(file1, file2))

    f1 = ZeusFile(file1) 
    f2 = ZeusFile(file2) 

    try: # try to compare the files

        # check that time stamps are the same
        t1 = f1.get_dset("t")[0]
        t2 = f2.get_dset("t")[0]
        if t1 != t2 and not force:
            raise ComparisonError("t", t1, t2)

        # check that the array dimensions are the same
        for axis in ['x1','x2','x3']:
            c1 = f1.get_dset(axis)
            c2 = f2.get_dset(axis)
            if c1.size != c2.size:
                raise ComparisonError(axis, c1.size, c2.size)

        # check that coordinates are the same
        for axis in ['x1','x2','x3']:
            c1 = f1.get_dset(axis)
            c2 = f2.get_dset(axis)
            try:
                assert_equality(c1,c2)
            except DifferenceError as e:
                e.var = axis
                raise e


        # check that velocities are the same
        for axis in ['v1','v2','v3']:
            c1 = f1.get_dset(axis)
            c2 = f2.get_dset(axis)
            try:
                assert_near_equality(c1,c2, rtol)
            except DifferenceError as DE:
                DE.var = axis

                if unforgiving:
                    raise DE
                else:
                    msg_str = "  Files do not match: {:} differs (max = {:8.2E}) "
                    print(msg_str.format(DE.var, DE.rerr.max()))
                    if verbose: DE.showall()

        # check that physical variables are the same
        for axis in ["e","d", "gp"]:
            c1 = f1.get_dset(axis)
            c2 = f2.get_dset(axis)
            try:
                assert_near_equality(c1,c2, rtol)
            except DifferenceError as DE:
                DE.var = axis

                if unforgiving:
                    raise DE
                else:
                    msg_str = "  Files do not match: {:} differs (max = {:8.2E}) "
                    print(msg_str.format(DE.var, DE.rerr.max()))
                    if verbose: DE.showall()
                

    except ComparisonError as CE:
        msg_str = "  Cannot compare files: {:} differs [{:18.12E} != {:18.12E}]"
        print(msg_str.format(CE.var, CE.value1, CE.value2))

    except DifferenceError as DE:
        if DE.var in ['x1','x2','x3']: # if coordinates differ
            msg_str = "  Cannot compare files: {:} differs"
            print(msg_str.format(DE.var))
        else:
            msg_str = "  Files do not match: {:} differs (max = {:8.2E}) "
            print(msg_str.format(DE.var, DE.diff.max()))
            if verbose: DE.showall()

    finally:
        f1.close()
        f2.close()

    return

def compare_output(output1, output2, rtol = 1e-8, 
                   unforgiving = True, verbose = True, force = False):
    
    for file1, file2 in zip(output1.files, output2.files):
        compare_two(file1,file2, rtol, unforgiving, verbose, force)

    return

class ZeusMPOutput:

    def __init__(self, datadir = "./"):
        self.datadir = datadir
        self.files = glob.glob(os.path.join(datadir, "hdfaa.???"))
        self.files.sort()



if __name__ == "__main__":
    pass
