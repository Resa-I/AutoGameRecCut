from Model.Frame_Capture.Capture_Sources.Frame_Capture_File import Frame_Capture_File
from Model.Frame_Capture.Capture_Sources.Frame_Capture_OBS import Frame_Capture_OBS
from Model.Frame_Capture.IFrameCaptureInterface import IFrameCaptureInterface


class FrameCaptureFactory:
    """Creates Frame Capture interface based on the provided configuration.   
    Called by the ModelController.
    """
    @staticmethod
    def create(config: dict) -> IFrameCaptureInterface:
        source =config.get('source', '')

        if source == "File":   
            return Frame_Capture_File()

        elif source == "OBS":
            return Frame_Capture_OBS()
            
        elif source == "Windows API":
            return Frame_Capture_File()
        # Placeholder - will be replaced with a Windows API implementation in a future version
        else:
            raise ValueError(f"Unknown capture type: {source}")