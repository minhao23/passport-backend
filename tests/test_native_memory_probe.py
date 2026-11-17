import io
import json
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

import native_memory_probe


class NativeProbeReportingTests(unittest.TestCase):
    def arguments(self, mask_only=False):
        return SimpleNamespace(
            app_dir="src",
            rounds=2,
            image=[],
            mask_only=mask_only,
        )

    def report(self, profile, with_jpeg=True):
        return {
            "profile": profile,
            "mask_hashes": {"portrait": "same-mask"},
            "jpeg_hashes": {"portrait": "same-jpeg"} if with_jpeg else {},
            "photo_errors": {} if with_jpeg else {"portrait": "PERSON_NOT_DETECTED"},
            "peak_mib": 1000.0 if profile == "reference" else 800.0,
        }

    def processes(self, reports):
        return [
            Mock(stdout="MEMORY_PROBE_RESULT=" + json.dumps(report))
            for report in reports
        ]

    def test_matching_native_outputs_report_peak_savings(self):
        reports = [self.report(profile) for profile in ("reference", "optimized")]
        output = io.StringIO()
        with (
            patch.object(
                native_memory_probe.subprocess,
                "run",
                side_effect=self.processes(reports),
            ) as run,
            redirect_stdout(output),
        ):
            native_memory_probe.compare(self.arguments())
        result = json.loads(output.getvalue())
        self.assertEqual(result["mask_parity"], "PASS")
        self.assertEqual(result["jpeg_parity"], "PASS")
        self.assertEqual(result["peak_reduction_mib"], 200)
        self.assertEqual(run.call_count, 2)
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["MALLOC_ARENA_MAX"], "2")
        self.assertEqual(environment["OMP_NUM_THREADS"], "1")
        self.assertEqual(environment["OPENBLAS_NUM_THREADS"], "1")
        self.assertEqual(environment["MKL_NUM_THREADS"], "1")

    def test_mask_only_does_not_claim_jpeg_verification(self):
        reports = [
            self.report(profile, with_jpeg=False)
            for profile in ("reference", "optimized")
        ]
        output = io.StringIO()
        with (
            patch.object(
                native_memory_probe.subprocess,
                "run",
                side_effect=self.processes(reports),
            ),
            redirect_stdout(output),
        ):
            native_memory_probe.compare(self.arguments(mask_only=True))
        self.assertEqual(json.loads(output.getvalue())["jpeg_parity"], "UNVERIFIED")

    def test_end_to_end_probe_requires_at_least_one_accepted_photo(self):
        reports = [
            self.report(profile, with_jpeg=False)
            for profile in ("reference", "optimized")
        ]
        with (
            patch.object(
                native_memory_probe.subprocess,
                "run",
                side_effect=self.processes(reports),
            ),
            redirect_stdout(io.StringIO()),
        ):
            with self.assertRaisesRegex(AssertionError, "No accepted portraits"):
                native_memory_probe.compare(self.arguments())

    def test_masks_jpegs_and_photo_errors_must_match(self):
        for field in ("mask_hashes", "jpeg_hashes", "photo_errors"):
            reference = self.report("reference")
            optimized = self.report("optimized")
            optimized[field] = {"changed": "different"}
            with (
                self.subTest(field=field),
                patch.object(
                    native_memory_probe.subprocess,
                    "run",
                    side_effect=self.processes([reference, optimized]),
                ),
            ):
                with self.assertRaisesRegex(AssertionError, field):
                    native_memory_probe.compare(self.arguments(mask_only=True))

    def test_missing_native_summary_is_an_error(self):
        with patch.object(
            native_memory_probe.subprocess, "run", return_value=Mock(stdout="No result")
        ):
            with self.assertRaisesRegex(RuntimeError, "Incomplete native probe"):
                native_memory_probe.compare(self.arguments())
