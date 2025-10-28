#import cv2

class Auto_rec_detect:
    """takes the latest frame from CaptureInterface and passes it to Frame_Analyzer_for_AutoRec for start/stop detection."""

    def __init__(self,f_analyzer_auto_Rec,f_capture_Source):
        self.f_analyzer_auto_Rec = f_analyzer_auto_Rec
        self.f_capture_Source =  f_capture_Source

    def set_frame_capture(self, capture_interface):
        self.f_capture_Source = capture_interface

    def auto_rec_detect(self, validated_data: dict) -> bool:
       
        lastframe,frame_index,fr_timestamp = self.f_capture_Source.get_latest_frame()

        if lastframe is None:
            print("lastframe ist None")

        if lastframe is not None:
            
            #-----Test-----
            #cv2.imshow("ROI", lastframe)
            #cv2.waitKey(1)  # 1 Sekunde anzeigen
            #cv2.imwrite('full_frame.jpg', frame)
            #print(f"Frames-----{frame_index}, {fr_timestamp}")  

                                                                        #Image coordinates for cutout
            trigger_start = self.f_analyzer_auto_Rec.check_roi_start(lastframe, 700, 800, 700, 1115)                                                                       
            trigger_stop = self.f_analyzer_auto_Rec.check_roi_end(lastframe, 100, 220, 600, 1250)
            
            #print(f"start-------{trigger_start}")
            #print(f"stop--------{trigger_stop}")


            if trigger_start == 1:
                return True
            if trigger_stop == 2:
                return False

            if trigger_stop == 3 or trigger_start== 4:
                print("Frame_Analyzer_for_AutoRec: -- nix detected")
