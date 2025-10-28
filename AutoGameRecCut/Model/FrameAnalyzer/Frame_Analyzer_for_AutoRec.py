import cv2
import easyocr
import re
#from datetime import datetime #Test

class Frame_Analyzer_for_AutoRec:
    def __init__(self, target1="aufwbrmphase", target2="warten auf spieler",
                 target3="sieg", target4="Niederlage", target5="unentschieden",
                 gpu=True, max_dist=3):
        self.target1 = target1.lower()
        self.target2 = target2.lower()
        self.target3 = target3.lower()
        self.target4 = target4.lower()
        self.target5 = target5.lower()
        self.reader = easyocr.Reader(['de'], gpu=gpu)
        self.max_dist = max_dist

    # Extracts a region of interest for Start -> reduce resources
    def check_roi_start(self, frame, y1, y2, x1, x2):
        roi = frame[y1:y2, x1:x2]
        if roi is None or roi.size == 0:
            print("ROI is empty or invalid")
            return 3
        return self.check_frame(roi)

    # Extracts a region of interest for End -> reduce resources
    def check_roi_end(self, frame, y1, y2, x1, x2):
        roi = frame[y1:y2, x1:x2]
        if roi is None or roi.size == 0:
            print("ROI is empty or invalid")
            return 3
        return self.check_frame(roi)

    #Checks a frame    
    def check_frame(self, frame):
        
        if frame is None or frame.size == 0:
            return 3

        proc = self.preprocess(frame)
        if proc is None:
            return 3
        
        #---Test------
        # cv2.imshow("ROI", proc)
        # cv2.waitKey(1)  # 1 Sekunde anzeigen
        # timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # filename = f"full_frame_{timestamp}.jpg"
        # cv2.imwrite(filename, proc)

        results = self.reader.readtext(proc)
        raw_text = " ".join([t[1].lower() for t in results])
        clean_text = re.sub(r'[^a-z0-9:aeoeueß]', ' ', raw_text)
        print("clean_text-- " + clean_text)

        start_targets = [self.target1, self.target2]
        end_targets = [self.target3, self.target4, self.target5]

        if self.fuzzy_match_any(clean_text, start_targets):
            return 1
        if self.fuzzy_match_any(clean_text, end_targets):
            return 2

   

        #Levenshtein function with early exit 
    def levenshtein_distance_max(self, s1, s2, max_dist=None):
        """
        Because EasyOCR does not recognize the text perfectly,
        max_dist = maximum number of allowed edits before aborting the calculation.
        """
        if max_dist is None:
            max_dist = self.max_dist
        if abs(len(s1) - len(s2)) > max_dist:
            return max_dist + 1

        if len(s1) < len(s2):
            s1, s2 = s2, s1

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            min_in_row = current_row[0]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
                min_in_row = min(min_in_row, current_row[-1])
            if min_in_row > max_dist:
                return max_dist + 1
            previous_row = current_row

        return previous_row[-1]

    #Checks if any target appears in the text
    def fuzzy_match_any(self, text, targets):
        """
        Checks if any target word or phrase appears in the text.
        Allows errors up to self.max_dist.
        """
        text_words = text.split()
        for target in targets:
            target_words = target.split()
            for i in range(len(text_words) - len(target_words) + 1):
                segment = " ".join(text_words[i:i + len(target_words)])

                #Dynamic fault tolerance:
                dyn_max = min(self.max_dist, max(1, len(target) // 2))

                dist = self.levenshtein_distance_max(segment, target, dyn_max)
                if dist <= dyn_max:
                    return True
        return False


    def preprocess(self, img):
        """
        for a better detection:
        Upscaling
        Grayscale conversion
        """
        if img is None or img.size == 0:
            return None

        sf = 2
        up = cv2.resize(img, None, fx=sf, fy=sf, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(gray)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        clean = cv2.morphologyEx(cl, cv2.MORPH_OPEN, kernel)
        return clean