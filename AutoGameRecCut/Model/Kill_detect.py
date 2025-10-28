from encodings import normalize_encoding
#import cv2 #test
  
class Kill_detect:
    """
    Detects kill events in captured frames and logs them in a List and returned.
    """
    def __init__(self,f_analyzer_kill,f_capture_Source=None):
        self.f_analyzer_kill = f_analyzer_kill
        self.f_capture_Source = f_capture_Source
       
        self.last_seen_frame_index = None
        self.previous_killscore = None

        self.killscore_list=[] 

        self.none_count = 0

    def set_frame_capture(self, capture_interface):
        self.f_capture_Source = capture_interface

    def kill_detect(self):
        lastframe,frame_index,fr_timestamp = self.f_capture_Source.get_latest_frame()
        if lastframe is not None:

            if frame_index == self.last_seen_frame_index:
                return False
            self.last_seen_frame_index = frame_index

            #----Test---
            #print(f"Frames-----{frame_index}, {fr_timestamp}")   
            #cv2.imshow("ROI", lastframe)
            #cv2.waitKey(1)

            #Detect killsign in the ROI = 1 to 5 or None        
            killscore = self.f_analyzer_kill.check_roi_for_kill_detect( #for 2 roi
                lastframe, 70,180,1530,1920 ,960,1055,930,990) # 1. top 2. bottum 3. left 4. right
            
            self.log_kill_event( killscore, frame_index, fr_timestamp,lastframe)

            #from def_save_event
            return self.killscore_list


    def log_kill_event(self, killscore, frame_index, fr_timestamp,lastframe):
        """
        Logs a kill event as START or END, handles consecutive None frames.
        
        """
        
        if killscore is not None and not (1 <= killscore <= 5):
            return
          
        # None-Handling
        if killscore is None:
            self.none_count += 1

            # End previous kill if None persists (end of round/death)
            if self.none_count >= 120 and self.previous_killscore is not None:
                self._save_event(
                    f"{self.previous_killscore},{frame_index-1},{fr_timestamp:.3f},END"
                )
                self.previous_killscore = None  # Reset
            return
        else:
            #Reset none_count when killscore appears again
            self.none_count = 0

        # Killscore changed or increased
        if (
            self.previous_killscore is None or
            killscore > self.previous_killscore or
            killscore != self.previous_killscore
        ):
            # End previous value
            if self.previous_killscore is not None:
                self._save_event(
                    f"{self.previous_killscore},{frame_index-1},{fr_timestamp:.3f},END"
                )

            # Start new valuet
            self._save_event(
                f"{killscore},{frame_index},{fr_timestamp:.3f},START"
            )
            #--Test---
            # filename = f"frame_{frame_index:04d}_{fr_timestamp:.0f}.jpg"
            # cv2.imwrite(filename,lastframe)

            # save current killscore
            self.previous_killscore = killscore
   

    def _save_event(self, line: str):
        """Saves a kill event to file and list."""
        # TXT
        with open("frames_log.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")

        # List append
        self.killscore_list.append(line)
         
    def finalize(self, final_frame_index=None, final_timestamp=None):
        if self.previous_killscore is not None:
            if final_frame_index is None:
                final_frame_index = self.last_seen_frame_index or 0
            if final_timestamp is None:
                final_timestamp = 0.0
            self._save_event(
                f"{self.previous_killscore},{final_frame_index},{final_timestamp:.3f},END"
            )
            self.previous_killscore = None
            self.none_count = 0

    def killscore_list_reset(self):
        print("killscore_list_reset")
        self.killscore_list = []
        self.previous_killscore = None
        self.none_count = 0
        self.last_seen_frame_index = None