import io, base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def to_img(fig, dpi: int = 120) -> str:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png', dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return 'data:image/png;base64,' + base64.b64encode(buf.read()).decode('ascii')


def plot_forecast(history_labels, history_values, labels, yhat, ylow=None, yhigh=None, color: str = '#10b981', title: str = '') -> str:
    fig, ax = plt.subplots(figsize=(6, 3))
    if history_labels and history_values:
        ax.plot(history_labels, history_values, label='History', color='#6b7280')
    if labels and yhat:
        if ylow is not None and yhigh is not None and len(ylow) == len(yhat) == len(yhigh):
            ax.fill_between(labels, ylow, yhigh, color=color, alpha=0.12)
        ax.plot(labels, yhat, label='Forecast', color=color, linestyle='--')
    ax.set_title(title)
    ax.legend(loc='lower center', ncol=2)
    ax.tick_params(axis='x', labelrotation=45)
    return to_img(fig)
