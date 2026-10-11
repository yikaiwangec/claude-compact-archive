# Compact instructions snippet

Append the section below to `~/.claude/CLAUDE.md` (every project) or to a project's `CLAUDE.md`. Adjust the
examples in brackets to the kind of work done there.

```markdown
## Compact instructions (apply to every compaction, manual or automatic)
- The full transcript is archived before every compaction (PreCompact hook, compact-archive plugin), so the
  summary can be short. Point to the archive or to saved files instead of restating long material.
- Keep MORE detail on the most recent work: the current task, open questions, the latest numbers and results,
  files just created or changed, [running jobs with their IDs, folders and expected finish times], and agreements
  with other people or sessions.
- Keep earlier material only where it still matters:
  - the user's decisions and standing rules;
  - final results, with their file paths;
  - errors already found and corrected, so they are not repeated.
- Drop dead-end back-and-forth, superseded drafts, intermediate numbers that were later corrected, and long tool
  output.
- Images do not survive compaction. Right after reading a screenshot, image or scanned page, write its key content
  out in text, and carry that text into the summary. After a compaction, do not claim that something matches an image
  without looking at it again.
- Keep, word for word and next to each result, the settings it depends on ([tolerances, which run or file is the
  valid one]) and any label such as "unverified", "placeholder", "do not use" or "preliminary". Never turn an
  unverified claim into a verified one in the summary.
- State the task state explicitly: what has been sent, launched or delivered, what is still only a draft, and every
  job still running ([workflows, agents, background commands, with their IDs and folders]).
- For code being worked on, keep the interfaces word for word, copied from the files rather than paraphrased:
  function signatures, the keys of dicts passed between modules, the columns of data and result files, array
  shapes. After a compaction, re-read them in the files before writing code that uses them; never write them from
  the summary.
- At natural breaks (a deliverable finished, a change of topic), suggest that the user run `/compact`.
```

The three rules on images, settings and task state come from an audit of real compactions (see
[smart-analysis.md](smart-analysis.md)). Two of the serious errors found after compactions were a claim about a
screenshot whose content had been lost, and a result reported without the warning that it came from placeholder data.
Among the wrong statements found in the summaries themselves, the commonest were task states, such as "not yet sent"
for something already sent.

The code rule comes from coding slips in the author's long research sessions after compactions: a dict key that was
not there, the wrong column of a data file (which changed a result silently), array shapes recalled wrongly. A replay
of the same tasks from the same summary, once each on two models (October 2026), found no slip in the tasks where the
model re-read the code first, and an interface slip in the task where it wrote straight away. The plugin's
post-compaction hook (SKILL.md, Step 1) reminds Claude of this after every compaction.
