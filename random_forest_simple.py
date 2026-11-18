"""Random Forest in plain words.

Idea: one decision tree is like asking ONE expert. A random forest asks MANY experts
(each sees a slightly different sample of the data) and takes a majority vote.
Many opinions averaged together are more reliable than a single one.

Task: predict whether a support ticket will be ESCALATED (1) or not (0).
Run: python random_forest_simple.py   (needs numpy, pandas, scikit-learn)
"""
import numpy as np  # numpy: fast maths and random numbers
import pandas as pd  # pandas: tables (DataFrames) of data
from sklearn.ensemble import RandomForestClassifier  # the random forest model itself
from sklearn.metrics import classification_report  # prints precision / recall / f1 per class
from sklearn.model_selection import train_test_split  # splits data into "study" and "exam" parts


def make_tickets(n=1000, seed=0) -> pd.DataFrame:  # builds n fake tickets; seed makes results repeatable
    """Fake data: tickets that are severe, old and have many replies escalate more often."""
    rng = np.random.default_rng(seed)  # random number generator with a fixed seed
    df = pd.DataFrame({  # create the table, one column per feature
        "severity": rng.integers(1, 5, n),        # random whole numbers 1-4; 1 = low ... 4 = critical
        "hours_open": rng.integers(1, 100, n),  # random hours the ticket has been open (1-99)
        "num_replies": rng.integers(0, 15, n),  # random number of replies (0-14)
    })
    score = df["severity"] * 1.0 + df["hours_open"] / 25 + df["num_replies"] / 5  # hidden "pressure" score: bigger = more likely to escalate
    df["escalated"] = (score + rng.normal(0, 1, n) > 7).astype(int)  # add noise, then label 1 if score passes 7 else 0
    return df  # hand the finished table back


class TicketEscalationModel:  # wraps the forest so training and prediction are tidy
    def __init__(self):  # runs once when you create the object
        # n_estimators = how many trees ("experts") vote
        # class_weight="balanced" = pay extra attention to the rare class (escalations)
        self.model = RandomForestClassifier(  # create the forest (not trained yet)
            n_estimators=100, max_depth=5, class_weight="balanced", random_state=0  # 100 trees, each at most 5 questions deep, fair to rare class, repeatable
        )
        self.features = ["severity", "hours_open", "num_replies"]  # the columns the model is allowed to look at

    def train(self, df: pd.DataFrame):  # teach the model and then test it
        # Hold back 25% of tickets the model never sees, so we can test it honestly
        X_train, X_test, y_train, y_test = train_test_split(  # X = inputs, y = correct answers
            df[self.features], df["escalated"], test_size=0.25, stratify=df["escalated"], random_state=0  # keep the same escalated share in both parts
        )
        self.model.fit(X_train, y_train)  # "fit" = learn from the study tickets
        print(classification_report(y_test, self.model.predict(X_test), target_names=["normal", "escalated"]))  # predict on unseen exam tickets and print the scorecard

    def predict_risk(self, severity, hours_open, num_replies) -> float:  # score one new ticket
        """Returns the share of trees voting 'escalate' (0.0 to 1.0)."""
        row = pd.DataFrame([[severity, hours_open, num_replies]], columns=self.features)  # put the ticket in a one-row table with the same column names
        return float(self.model.predict_proba(row)[0, 1])  # probability of class 1 (escalated), as a plain number

    def what_matters(self) -> pd.Series:  # which inputs drove the decisions
        """Which inputs did the forest rely on most?"""
        return pd.Series(self.model.feature_importances_, index=self.features).sort_values(ascending=False)  # importance per feature (sums to 1), biggest first


if __name__ == "__main__":  # only runs when you execute this file directly
    tickets = make_tickets()  # create the fake data
    print("share escalated:", round(tickets["escalated"].mean(), 2))  # mean of a 0/1 column = fraction of escalated tickets

    m = TicketEscalationModel()  # make the model object
    m.train(tickets)  # train and print the scorecard

    print("critical, old, busy ticket ->", round(m.predict_risk(4, 90, 12), 2))  # expect a high risk
    print("low, new, quiet ticket     ->", round(m.predict_risk(1, 2, 0), 2))  # expect a low risk
    print(m.what_matters().round(2))  # show which features mattered most

    assert m.predict_risk(4, 90, 12) > 0.8 > 0.2 > m.predict_risk(1, 2, 0)  # self-check: high ticket > 0.8 and low ticket < 0.2
