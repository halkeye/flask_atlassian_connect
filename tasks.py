from invoke import task


@task
def docs(ctx):
    """Build docs into build directory"""
    ctx.run("pip install -r requirements/docs.txt")
    ctx.run("python -msphinx -b html ./docs ./docs/build")


@task
def test(ctx):
    """Run all the tests"""
    ctx.run("python -m pytest", pty=True)
