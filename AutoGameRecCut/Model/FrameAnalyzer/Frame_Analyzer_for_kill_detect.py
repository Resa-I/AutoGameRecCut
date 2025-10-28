import os
from datetime import datetime
import cv2
#import easyocr
# import re  #for Removing special characters in OCR 

                                                  #threshold:  Too many at 84
                                                            # Too few at 85
class Frame_Analyzer_for_kill_detect: 
    """
    If, for example, kill_sign 5 (t2-5.jpg)  has a match, the filename from kill_signs is shortened and killscore2 = 5 is returned.
    def check_frame_Kill_feed Will be implemented in a future version.
    """
    def __init__(self, target1="Res092",gpu=True,                   
                num_templates: int = 20, threshold: float = 0.845):
        self.target1 = target1.lower()
        #self.reader = easyocr.Reader(['de'], gpu=gpu)

        self.num_templates = num_templates
        self.threshold = threshold

        #Base path: location of current file for matching
        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.resource_dir = os.path.join(BASE_DIR, "Ressourcen", "kill_signs")
        self.templates = self._load_templates_in_dict()

        #Called by KillDetect
    def check_roi_for_kill_detect(self, frame, y1, y2, x1, x2 ,y1x,y2x, x1x,x2x):
        roi1 = frame[y1:y2, x1:x2] # for kill feed (OCR)
        roi2 = frame[y1x:y2x, x1x:x2x] # for bottom kill counter (template matching)

        return self.check_frame(roi1, roi2)

    def check_frame(self, frame1roi, frame2roi):
        #killscore1=self.check_frame_Kill_feed(frame1roi)
        killscore2=self.check_frame_u_mid(frame2roi)
        #print("-----killfeed         -detected:   "+ killscore1)
        #print("-----kill counter bottum -detected:   "+ killscore2)
        print("\n")

        return killscore2
    
    def check_frame_Kill_feed(self,frame1roi):
        proc1 = self.preprocess(frame1roi)
         #Levenshtein funktion... 

        # results1 = self.reader.readtext(proc1)
        # raw_text1   = " ".join([t[1].lower() for t in results1])
        # clean_text1 = re.sub(r'[^a-z0-9:aeoeueß]', ' ', raw_text1)
             
        # if self.target1 in clean_text and clean_text != self.last_text:
        #     self.last_text = clean_text
        #     return 1   # new Kill
        # return 3      # no new Kill

    def check_frame_u_mid(self, frame2roi):
         
        if frame2roi.size is None or frame2roi.size == 0:
            return None
        
        proc2 = self.preprocess(frame2roi)

        #----Test----------
        # cv2.imshow("ROI", proc1)
        # cv2.waitKey(1)
        # cv2.imshow("ROI", proc2)
        # cv2.waitKey(1)  
        # cv2.imwrite('full_frame2.jpg', proc2)
        #cv2.imwrite(f"roiframe_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg", proc2)
        
        best_score = -1
        best_id = None

        # Compare ROI with all templates
        for key, templ in self.templates.items():
            res = cv2.matchTemplate(proc2, templ, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            if max_val > best_score:
                best_score = max_val
                best_id = key

        if best_score >= self.threshold:
             
            killscore= int(best_id[-1]) 

            print(f"Killcount detected {killscore} Max Score={best_score:.2f}")
            return killscore
        else:
            killscore =None
            print(f"No Kill-Sign detected {killscore} Max Score={best_score:.2f}")   
            return killscore

        

    def preprocess(self, img):
        # 1. Upscale
        sf = 2
        up = cv2.resize(img, None, fx=sf, fy=sf, interpolation=cv2.INTER_CUBIC)

        # 2. Grayscale
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)

        # 3. CLAHE (local contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl = clahe.apply(gray)

        # 4. Morphological opening for noise reduction
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
        clean = cv2.morphologyEx(cl, cv2.MORPH_OPEN, kernel)

        return clean

        #Loads all JPG images in resource_dir into a dictionary 
        #Filename is shortened
    def _load_templates_in_dict(self):
        templates = {}
        for filename in os.listdir(self.resource_dir):
            if filename.lower().endswith(".jpg"):
                path = os.path.join(self.resource_dir, filename)
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)# preprocess
                if img is None:
                    raise FileNotFoundError(f"Template not found: {path}")
                key = os.path.splitext(filename)[0]  # Dataname without .jpg as Key
                templates[key] = img
        return templates
