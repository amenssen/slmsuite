"""
Hardware control for AlliedVision cameras via the :mod:`vimba` interface.
Install :mod:`vimba` by following the
`provided instructions <https://github.com/alliedvision/VimbaPython>`_.
Include the ``numpy-export`` flag in the ``pip install`` command,
as the :class:`AlliedVision` class makes use of these features. See especially the
`vimba python manual <https://github.com/alliedvision/VimbaPython/blob/master/Documentation/Vimba%20Python%20Manual.pdf>`_
for reference.
"""
import sys
import time
import numpy as np
from vimba import Frame,AllocationMode
from vimba import Camera as VimbaCam
from slmsuite.hardware.cameras.camera import Camera
from typing import Optional, Tuple

try:
    import vimba
except ImportError:
    print("alliedvision.py: vimba not installed. Install to use AlliedVision cameras.")


class AlliedVision(Camera):
    r"""
    AlliedVision camera.

    Attributes
    ----------
    sdk : vimba.Vimba
        AlliedVision SDK. Shared among instances of :class:`AlliedVision`.
    cam : vimba.Camera
        Object to talk with the desired camera.

    Caution
    ~~~~~~~~
    The AlliedVision SDK :mod:`vimba` includes protections to maintain camera connectivity:
    specifically, the SDK :class:`vimba.Vimba` and cameras :class:`vimba.Camera` are designed
    to be used in concert with ``with`` statements. Unfortunately, this does not mesh with the
    architecture of :mod:`slmsuite`, where notebook-style operation is desired.
    Using ``with`` statements inside :class:`.AlliedVision` methods is likewise not an option,
    as the methods to :meth:`__enter__()` and :meth:`__exit__()` the ``with`` are time-consuming
    due to calls to :meth:`_open()` and :meth:`_close()` the objects, to the point of
    :math:`\mathcal{O}(\text{s})` overhead. :class:`.AlliedVision` disables these protections by
    calling :meth:`__enter__()` and :meth:`__exit__()` directly during :meth:`.__init__()` and
    :meth:`.close()`, instead of inside ``with`` statements.
    """

    sdk = None

    def __init__(self, serial="", verbose=True, **kwargs):
        """
        Initialize camera and attributes.

        Parameters
        ----------
        serial : str
            Serial number of the camera to open. If empty, defaults to the first camera in the list
            returned by :meth:`vimba.get_all_cameras()`.
        verbose : bool
            Whether or not to print extra information.
        kwargs
            See :meth:`.Camera.__init__` for permissible options.
        """
        if AlliedVision.sdk is None:
            if verbose:
                print("vimba initializing... ", end="")
            AlliedVision.sdk = vimba.Vimba.get_instance()
            AlliedVision.sdk.__enter__()
            if verbose:
                print("success")

        if verbose:
            print("Looking for cameras... ", end="")
        camera_list = AlliedVision.sdk.get_all_cameras()
        if verbose:
            print("success")

        serial_list = [cam.get_serial() for cam in camera_list]
        if serial == "":
            if len(camera_list) == 0:
                raise RuntimeError("No cameras found by vimba.")
            if len(camera_list) > 1 and verbose:
                print("No serial given... Choosing first of ", serial_list)

            self.cam = camera_list[0]
            serial = self.cam.get_serial()
        else:
            if serial in serial_list:
                self.cam = camera_list[serial_list.index(serial)]
            else:
                raise RuntimeError(
                    "Serial " + serial + " not found by vimba. Available: ", serial_list
                )

        if verbose:
            print("vimba sn " "{}" " initializing... ".format(serial), end="")
        self.cam.__enter__()
        if verbose:
            print("success")

        super().__init__(
            self.cam.SensorWidth.get(),
            self.cam.SensorHeight.get(),
            bitdepth=int(self.cam.PixelSize.get()),
            dx_um=None,
            dy_um=None,
            name=serial,
            **kwargs
        )

        self.cam.BinningHorizontal.set(1)
        self.cam.BinningVertical.set(1)

        self.cam.GainAuto.set("Off")

        self.cam.ExposureAuto.set("Off")
        self.cam.ExposureMode.set("Timed")

        self.cam.AcquisitionMode.set("SingleFrame")

        # Future: triggered instead of SingleFrame.
        self.cam.TriggerSelector.set("AcquisitionStart")
        self.cam.TriggerMode.set("Off")
        self.cam.TriggerActivation.set("RisingEdge")
        self.cam.TriggerSource.set("Software")
        self.frame_storage=[]
    def close(self, close_sdk=True):
        """
        See :meth:`.Camera.close`

        Parameters
        ----------
        close_sdk : bool
            Whether or not to close the :mod:`vimba` instance.
        """
        self.cam.__exit__(None, None, None)

        if close_sdk:
            self.close_sdk()

    @staticmethod
    def info(verbose=True):
        """
        Discovers all Thorlabs scientific cameras.

        Parameters
        ----------
        verbose : bool
            Whether to print the discovered information.

        Returns
        --------
        list of str
            List of AlliedVision serial numbers.
        """
        if AlliedVision.sdk is None:
            AlliedVision.sdk = vimba.Vimba.get_instance()
            AlliedVision.sdk.__enter__()
            close_sdk = True
        else:
            close_sdk = False

        camera_list = AlliedVision.sdk.get_all_cameras()
        serial_list = [cam.get_serial() for cam in camera_list]

        if verbose:
            print("AlliedVision serials:")
            for serial in serial_list:
                print("\"{}\"".format(serial))

        if close_sdk:
            AlliedVision.close_sdk()

        return serial_list

    @classmethod
    def close_sdk(cls):
        """
        Close the :mod:`vimba` instance.
        """
        if cls.sdk is not None:
            cls.sdk.__exit__(None, None, None)
            cls.sdk = None

    ### Property Configuration ###

    def get_properties(self, properties=None):
        """
        Print the list of camera properties.

        Parameters
        ----------
        properties : dict or None
            The target camera's property dictionary. If ``None``, the property
            dictionary is fetched from the camera associated with the calling instance.
        """
        if properties is None:
            properties = self.cam.__dict__.keys()

        for key in properties:
            prop = self.cam.__dict__[key]
            try:
                print(prop.get_name(), end="\t")
            except BaseException as e:
                print("Error accessing property dictionary, '{}':{}".format(key, e))
                continue

            try:
                print(prop.get(), end="\t")
            except:
                pass

            try:
                print(prop.get_unit(), end="\t")
            except:
                pass

            try:
                print(prop.get_description(), end="\n")
            except:
                print("")

    def set_adc_bitdepth(self, bitdepth):
        """
        Set the digitization bitdepth.

        Parameters
        ----------
        bitdepth : int
            Desired digitization bitdepth.
        """
        bitdepth = int(bitdepth)

        for entry in self.cam.SensorBitDepth.get_all_entries():
            value = entry.as_tuple()  # (name : str, value : int)
            if str(bitdepth) in value[0]:
                self.cam.SensorBitDepth.set(value[1])
                break
            raise RuntimeError("ADC bitdepth {} not found.".format(bitdepth))
    def set_pixel_format(self,index):
         # Get pixel formats available in the camera
        fmts = self.cam.get_pixel_formats()

        # In this case , we want a format that supports colors
        #fmts = intersect_pixel_formats(fmts , COLOR_PIXEL_FORMATS)

        # In this case , we want a format that is compatible with OpenCV
        #fmts = intersect_pixel_formats(fmts , OPENCV_PIXEL_FORMATS)

        if fmts:
            self.cam.set_pixel_format(fmts[index])

        else:
            print('Abort. No valid pixel format found.')
    def get_adc_bitdepth(self):
        """
        Get the digitization bitdepth.

        Returns
        -------
        int
            The digitization bitdepth.
        """
        value = str(self.cam.SensorBitDepth.get())
        bitdepth = int("".join(char for char in value if char.isdigit()))
        return bitdepth

    def get_exposure(self):
        """See :meth:`.Camera.get_exposure`."""
        return float(self.cam.ExposureTime.get()) / 1e6

    def set_exposure(self, exposure_s):
        """See :meth:`.Camera.set_exposure`."""
        self.cam.ExposureTime.set(float(exposure_s * 1e6))

    def set_woi(self, woi=None,mult=8):
        """See :meth:`.Camera.set_woi`."""

           #woi is [x_coord,delta_x,y_coord,delta_y], where x and y coordinates are at the centre of the woi.
        if woi != None:
            x_out=woi[0]-8
            roi_deltax=woi[1]+16
            y_out=woi[2]-8
            roi_deltay=woi[3]+16
            
            roi_deltax=mult*np.ceil(roi_deltax/mult)
            roi_deltay=mult*np.ceil(roi_deltay/mult)
            #x_out=int(2*round(x_out/2))
            #y_out=int(2*round(y_out/2))
            cam=self.cam
            cam.Height.set(roi_deltay) 
            cam.Width.set(roi_deltax) 
            offsetx_calc = int(x_out) - np.mod(int(x_out),2)
            offsety_calc = int(y_out) - np.mod(int(y_out),2)
            cam.OffsetX.set(offsetx_calc) 
            cam.OffsetY.set(offsety_calc) 

            return np.array([x_out,roi_deltax,y_out,roi_deltay])
        else:
            return
    
    # def frame_handler(self, cam, frame):
    #     if frame.get_status() == FrameStatus.Complete:
    #         # Store the frame's data as a numpy array
    #         
    #     cam.queue_frame(frame)
    def frame_handler(self,cam: VimbaCam, frame: Frame):
       # print('{} acquired {}'.format(cam, frame), flush=True)
        self.frame_storage=frame.as_numpy_ndarray()
        cam.queue_frame(frame)
    
    def parse_args(self) -> Tuple[Optional[str], AllocationMode]:
        args = sys.argv[1:]
        argc = len(args)

        allocation_mode = AllocationMode.AnnounceFrame
        cam_id = ""
        for arg in args:
            if arg in ('/h', '-h'):
                print_usage()
                sys.exit(0)
            elif arg in ('/x', '-x'):
                allocation_mode = AllocationMode.AllocAndAnnounceFrame
            elif not cam_id:
                cam_id = arg

        if argc > 2:
            abort(reason="Invalid number of arguments. Abort.", return_code=2, usage=True)

        return (cam_id if cam_id else None, allocation_mode)
    
    def start_streaming_images(self, buffer_count=10):
        print('Starting image stream...')
        self.cam.AcquisitionMode.set("Continuous")

        #cam_id, allocation_mode = self.parse_args()
        self.cam.start_streaming(handler=self.frame_handler, buffer_count=buffer_count)#,allocation_mode=allocation_mode)
        #cam.start_streaming(handler=frame_handler, buffer_count=10, allocation_mode=allocation_mode)

    def stop_streaming_images(self):
        print('Stopping image stream...')
        self.cam.stop_streaming()
        self.cam.AcquisitionMode.set("SingleFrame")
    def get_captured_images(self, clear_after=True):
        """
        Retrieve captured images and optionally clear the storage after retrieval.

        Parameters:
            clear_after (bool): Whether to clear the stored images after retrieving them.

        Returns:
            list of numpy.ndarray: List containing the captured image data.
        """
        images = self.frame_storage[:,:,0]

        return images
    
    
    def get_image(self, timeout_s=1):
        """See :meth:`.Camera.get_image`."""
        t = time.time()

        # Convert timeout_s to ms
        frame = self.cam.get_frame(timeout_ms=int(1e3 * timeout_s))
        frame = frame.as_numpy_ndarray()
        if np.amax(frame) == 510:
            print("lol")
        # We have noticed that sometimes the camera gets into a state where
        # it returns a frame of all zeros apart from one pixel with value of 31.
        # This method is admittedly a hack to try getting a frame a few more times.
        # We welcome contributions to fix this. or np.amax(frame) == 510
        while np.sum(frame) == np.amax(frame) == 31 or np.amax(frame) == 510 and time.time() - t < timeout_s:
            frame = self.cam.get_frame(timeout_ms=int(1e3 * timeout_s))
            frame = frame.as_numpy_ndarray()

        return self.transform(np.squeeze(frame))

    def flush(self, timeout_s=1e-3):
        """See :meth:`.Camera.flush`."""
        pass

    def reset(self):
        """See :meth:`.Camera.reset`."""
        raise NotImplementedError()
