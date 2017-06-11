from invoke import task


@task
def test(ctx):
    ctx.run("python -m pytest", pty=True)
