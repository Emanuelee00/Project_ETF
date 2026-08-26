import matplotlib.pyplot as plt

def plot_equity(df, title="Equity Curve"):
    plt.figure()
    plt.plot(df['equity'])
    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Equity")
    plt.grid()
    plt.show()