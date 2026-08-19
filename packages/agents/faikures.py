class WorkflowFailureInjector:
    def __init__(self):
        self.fail_analyze_once = False

    def should_fail_analyze(self) -> bool:
        if self.fail_analyze_once:
            self.fail_analyze_once = False
            return True

        return False