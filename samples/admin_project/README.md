This directory holds source media for the sample admin project.

Files:

* `blocks/block-001/welcome.mp3`
* `blocks/block-001/syllabus.pdf`
* `blocks/block-002/lesson.wav`

Generate the distributable bundle (uses the test KDF profile so it opens quickly):

```bash
python scripts/generate_sample_bundle.py
```

Output: `samples/Sample_Course.audiobundle` and `samples/Sample_Course-passwords.txt`

The password list is a sidecar next to the bundle, not stored in `project.json`. Course folders are a single top level (Day 1, Day 2, …); sequence is per day. See [COURSE_STRUCTURE.md](../../docs/COURSE_STRUCTURE.md).

Sample passwords (documentation only; never used in production projects):

* Main: `sample-main`
* Introduction: `sample-intro`
* Lesson 1: `sample-lesson`
* Exercises: `sample-exercises`
