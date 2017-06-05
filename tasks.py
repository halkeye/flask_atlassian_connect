from invoke import task


@task
def dev(ctx):
    ctx.run("PORT=3000 AC_BASE_URL=https://dev.gavinmogan.com python web.py")


@task
def view(ctx):
    import pickle
    print repr(pickle.load(open('clients.pk')))
    # ctx.run("python -mpickle clients.pk")


@task
def test(ctx):
    ctx.run("python -m pytest", pty=True)
