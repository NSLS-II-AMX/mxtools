from .flyer import MXFlyer

class MXRasterFlyer(MXFlyer):
    def __init__(self, vector, zebra, detector) -> None:
        self.name = "MXRasterFlyer"
        super().__init__(vector, zebra, detector)

    def update_parameters(self, *args, **kwargs):
        self.configure_detector(**kwargs)
        self.configure_vector(**kwargs)
        self.configure_zebra(**kwargs)

    def configure_detector(self, **kwargs):
        file_prefix = kwargs["file_prefix"]
        data_directory_name = kwargs["data_directory_name"]
        self.detector.file.external_name.put(file_prefix)
        self.detector.file.write_path_template = data_directory_name
        self.detector.file.file_write_images_per_file.put(kwargs["num_images_per_file"])

    # expected zebra setup:
    #     time in ms
    #     Posn direction: positive
    #     gate trig source - Position
    #     pulse trig source - Time
    def setup_zebra_vector_scan(
        self,
        angle_start,
        gate_width,
        scan_width,
        pulse_width,
        pulse_step,
        exposure_period_per_image,
        num_images,
        is_still=False,
    ):
        self.zebra.pc.gate.start.put(angle_start)
        if is_still is False:
            self.zebra.pc.gate.width.put(gate_width)
            self.zebra.pc.gate.step.put(scan_width)
        self.zebra.pc.gate.num_gates.put(num_images)
        self.zebra.pc.pulse.start.put(0)
        self.zebra.pc.pulse.width.put(pulse_width)
        self.zebra.pc.pulse.step.put(pulse_step)
        self.zebra.pc.pulse.delay.put(exposure_period_per_image / 2 * 1000)
        self.zebra.pc.pulse.max.put(num_images)

    def detector_arm(self, **kwargs):
        start = kwargs["angle_start"]
        width = kwargs["img_width"]
        num_images = kwargs["num_images"]
        exposure_per_image = kwargs["exposure_period_per_image"]
        file_prefix = kwargs["file_prefix"]
        data_directory_name = kwargs["data_directory_name"]
        file_number_start = kwargs["file_number_start"]
        x_beam = kwargs["x_beam"]
        y_beam = kwargs["y_beam"]
        wavelength = kwargs["wavelength"]
        det_distance_m = kwargs["det_distance_m"]

        self.detector.cam.save_files.put(1)
        self.detector.cam.file_owner.put(getpass.getuser())
        self.detector.cam.file_owner_grp.put(grp.getgrgid(os.getgid())[0])
        self.detector.cam.file_perms.put(420)
        file_prefix_minus_directory = str(file_prefix)
        file_prefix_minus_directory = file_prefix_minus_directory.split("/")[-1]

        self.detector.cam.acquire_time.put(exposure_per_image)
        self.detector.cam.acquire_period.put(exposure_per_image)
        self.detector.cam.num_images.put(num_images)
        self.detector.cam.num_triggers.put(1)
        self.detector.cam.file_path.put(data_directory_name)
        self.detector.cam.fw_name_pattern.put(f"{file_prefix_minus_directory}_$id")

        self.detector.cam.sequence_id.put(file_number_start)

        # originally from detector_set_fileheader
        self.detector.cam.beam_center_x.put(x_beam)
        self.detector.cam.beam_center_y.put(y_beam)
        self.detector.cam.omega_incr.put(width)
        self.detector.cam.omega_start.put(start)
        self.detector.cam.wavelength.put(wavelength)
        self.detector.cam.det_distance.put(det_distance_m)
        self.detector.cam.trigger_mode.put(eiger.EXTERNAL_SERIES)

