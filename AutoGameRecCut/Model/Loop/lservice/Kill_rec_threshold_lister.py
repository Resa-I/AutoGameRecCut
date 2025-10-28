from typing import List, Dict, Any, Tuple


class Kill_rec_threshold_lister:
    """
    Filters killscore logs (strings "idx,frame,time,START/END").

      - Forms sequences from consecutive START entries whose idx increases by +1.
      - Keeps only sequences where max(idx) >= threshold (>= 1).
      - If a sequence is kept, all STARTs in the sequence are retained.
      - For each kept START, the first following END with the same idx is also retained (if exists).
      - Result: original lines in original order.
    """

    @staticmethod
    def _parse_lines(lines: List[str]) -> List[Dict[str, Any]]:
        """Parses lines into structured entries; invalid lines are ignored."""
        parsed: List[Dict[str, Any]] = []
        for orig_i, raw in enumerate(lines):
            s = raw.strip()
            if not s:
                continue
            parts = s.split(",")
            if len(parts) != 4:
                continue
            idx_s, frame_s, time_s, tag = parts
            try:
                idx = int(idx_s)
            except ValueError:
                continue
            parsed.append({
                "idx": idx,
                "frame": frame_s,
                "time": time_s,
                "tag": tag.strip().upper(),
                "line": raw,
                "orig_i": orig_i
            })
        return parsed

    @staticmethod
    def _collect_start_positions(parsed: List[Dict[str, Any]]) -> List[int]:
        """Returns the indices in `parsed` of all START entries."""
        return [i for i, p in enumerate(parsed) if p["tag"] == "START"]

    def filter_lines(self, lines: List[str], threshold: int) -> List[str]:
        """
        Filters the input list and returns the filtered original lines.
        - lines: list of strings (original lines)
        - threshold: integer >= 1 (minimum idx value to keep a sequence)
        """
        if threshold < 1:
            raise ValueError("threshold must be >= 1")

        parsed = self._parse_lines(lines)
        if not parsed:
            return []

        start_positions = self._collect_start_positions(parsed)
        if not start_positions:
            return []

        starts_vals = [parsed[pos]["idx"] for pos in start_positions]

        # 1) Form sequences: consecutive STARTs where idx increments by 1
        series: List[List[Tuple[int, int]]] = []  # Serie = List[(parsed_pos, idx)]
        cur_series: List[Tuple[int, int]] = []
        for pos, val in zip(start_positions, starts_vals):
            if not cur_series:
                cur_series.append((pos, val))
            else:
                prev_idx = cur_series[-1][1]
                if val == prev_idx + 1:
                    cur_series.append((pos, val))
                else:
                    series.append(cur_series)
                    cur_series = [(pos, val)]
        if cur_series:
            series.append(cur_series)

        # 2) Determine which series to keep (max(idx) >= threshold)
        keep_start_parsed_positions = set()
        for ser in series:
            max_idx = max(val for _, val in ser)
            if max_idx >= threshold:
                for parsed_pos, _ in ser:
                    keep_start_parsed_positions.add(parsed_pos)

        if not keep_start_parsed_positions:
            return []

        # 3) For each kept START: keep START and first following END with same idx
        keep_orig_indices = set()
        for start_parsed_pos in sorted(keep_start_parsed_positions):
            start_entry = parsed[start_parsed_pos]
            keep_orig_indices.add(start_entry["orig_i"])
            # Suche erste END mit gleicher idx nach start_parsed_pos
            for j in range(start_parsed_pos + 1, len(parsed)):
                if parsed[j]["idx"] == start_entry["idx"] and parsed[j]["tag"] == "END":
                    keep_orig_indices.add(parsed[j]["orig_i"])
                    break

        # 4) Return lines in original order
        kept_lines = [lines[i] for i in sorted(keep_orig_indices)]
        return kept_lines

    def filter_with_indices(self, lines: List[str], threshold: int) -> Tuple[List[str], List[int]]:
        """
        Same as filter_lines, but also returns the original indices of the kept lines.
        """
        kept_lines = self.filter_lines(lines, threshold)
        kept_indices = [i for i, _ in enumerate(lines) if lines[i] in kept_lines]
        return kept_lines, kept_indices

