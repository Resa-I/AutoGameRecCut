 

class Detect_gpu:

    def __init__(self,gui_controller,model_controller):
        self.gui_controller = gui_controller
        self.model_controller = model_controller
           
        self._detect_gpu()
    
    def _detect_gpu(self):
        import torch #on the top utf-8 problems....
        if torch.cuda.is_available():
            self.gui_controller.set_gpu_info(torch.cuda.get_device_name(0))
            self.model_controller.set_gpu_info(torch.cuda.get_device_name(0))
        else:
            self.gui_controller.set_gpu_info( "GPU not detected----")
            self.model_controller.set_gpu_info("GPU not detected----")

