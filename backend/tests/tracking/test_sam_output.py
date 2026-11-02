from pathlib import Path

from standard_motion.tracking.sam_output import parse_boxes

# Frames 0 and 2 of a real SAM 3.1 response (episode 3, gripper box prompt).
SAM_SAMPLE = (Path(__file__).parent / "sam_sample.txt").read_text()


def test_parses_frames_ids_boxes_and_confidence():
    boxes = parse_boxes(SAM_SAMPLE)

    assert [b.frame for b in boxes] == [0, 2]
    assert {b.object_id for b in boxes} == {"1"}
    first = boxes[0]
    # The parser converts SAM's inclusive corners to half-open bounds.
    assert (first.left, first.top, first.right, first.bottom) == (186, 49, 221, 82)
    assert first.confidence is not None
    assert abs(first.confidence - 0.86328125) < 1e-9


def test_empty_output_means_no_detections():
    assert parse_boxes("") == []
