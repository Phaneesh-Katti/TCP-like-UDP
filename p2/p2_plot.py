import pandas as pd
import matplotlib.pyplot as plt

# Load CSV data
data = pd.read_csv("p2_fairness.csv")

# Calculate average JFI for each delay value
avg_jfi = data.groupby("delay")["jfi"].mean().reset_index()

# Plotting JFI as a function of link delay
plt.figure(figsize=(10, 6))
plt.plot(avg_jfi['delay'], avg_jfi['jfi'], marker='o', color='b', label="Average Jain's Fairness Index")
plt.xlabel("Link Delay (ms)")
plt.ylabel("Average Jain's Fairness Index (JFI)")
plt.title("Average Jain's Fairness Index as a Function of Link Delay")
plt.legend()
plt.grid()
plt.show()
