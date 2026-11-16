.PHONY: check eval

# Fresh clone: network is used only to install packages. No GitHub token, no model key.
# Review quality on real pull requests is not measured here.
check:
	python3 -m pip install -q -r requirements.txt
	GITHUB_TOKEN= DEEPSEEK_API_KEY= python3 -m pytest tests -q --cov=agents --cov=graph --cov=tools --cov=api --cov-report=term-missing
	GITHUB_TOKEN= DEEPSEEK_API_KEY= python3 eval/run_cases.py

eval:
	GITHUB_TOKEN= DEEPSEEK_API_KEY= python3 eval/run_cases.py
