import matplotlib.pyplot as plt

color_dic = {
    "0" : "green",
    "1" : "blue",
    "2" : "red",
    "3" : "yellow",
    "4" : "black"
}

def printChart(printing_list):
    i = 0
    fig, ax = plt.subplots()
    tasks_list = []
    for item in printing_list:
        if item[0] != -1:
            ax.broken_barh([(i, 1)], (3 * item[0] - 1, 2), facecolors = color_dic[str(item[1])])
        if item[0] == -1:
            ax.broken_barh([(i, 1)], (1, 1), facecolors = "white")
        i += 1
        if "Task " + str(item[0]) not in tasks_list and item[0] > 0:
            tasks_list.append("Task " + str(item[0]))
    tasks_list.sort()
    ax.set_yticks([(i + 1) * 3 for i in range(len(tasks_list))])
    ax.set_yticklabels(tasks_list)
    plt.show()
