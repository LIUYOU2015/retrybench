import tempfile
import unittest
from pathlib import Path

from retrybench.paper_assets import generate_paper_assets


class PaperAssetTests(unittest.TestCase):
    def test_generated_assets_match_checked_in_evidence(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            paths = generate_paper_assets(root, Path(directory))
            self.assertEqual(len(paths), 4)
            model = (Path(directory) / "table-model-results.tex").read_text()
            closest = (Path(directory) / "table-closest-work.tex").read_text()
            frameworks = (Path(directory) / "table-framework-audits.tex").read_text()
            figure = (Path(directory) / "figure-task-robustness.svg").read_text()
            self.assertIn("51/60", model)
            self.assertIn("30/60", model)
            self.assertIn("12/24", closest)
            self.assertIn("24/24", closest)
            self.assertEqual(frameworks.count("12"), 2)
            self.assertIn("artifact", figure)
            self.assertIn("Mean (95% t CI)", figure)
            self.assertTrue(figure.startswith("<?xml"))


if __name__ == "__main__":
    unittest.main()
