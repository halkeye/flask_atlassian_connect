pipeline {
  agent {
    docker {
      image 'python:3.6.2'
    }
  }

  options {
    timeout(time: 10, unit: 'MINUTES')
    ansiColor('xterm')
  }

  stages {
    stage('Before Install') {
      steps {
        sh """
          pip install --upgrade pip
          pip install --upgrade setuptools
          pip install --upgrade pytest
          pip --version
          """
      }
    }

    stage('Install') {
      steps {
        sh """
          ls -l
          pwd
          python setup.py -q install
          python setup.py sdist
          pip install -r requirements/dev.txt
          """
      }
    }

    stage('Test') {
      steps {
        sh 'py.test'
      }
    }

    stage('Docs') {
      steps {
        sh "invoke docs"
      }
    }

    stage('Deploy Docs (Github)') {
      when { branch 'master' }
      environment {
        GITHUB = credentials('github-halkeye')
        DEPLOY_DIRECTORY = 'docs/build'
        DEPLOY_BRANCH = 'gh-pages'
      }
      steps {
        sh "git worktree add -B ${env.DEPLOY_BRANCH} ${env.DEPLOY_DIRECTORY} origin/${env.DEPLOY_BRANCH}"
        sh "rm -rf ${env.DEPLOY_DIRECTORY}/*"

        dir(env.DEPLOY_DIRECTORY) {
          sh 'git add --all && git commit -m "Publishing to gh-pages"'
          sh "git remote add deploy ${env.GIT_URL.replace("https://", "https://${GITHUB_USR}:${GITHUB_PSW}@")}"
          sh "git push deploy"
          sh "git remote remove deploy"
        }
      }
    }
  }
  post {
    failure {
      emailext(
        attachLog: true,
        recipientProviders: [developers()],
        body: "Build failed (see ${env.BUILD_URL})",
        subject: "[JENKINS] ${env.JOB_NAME} failed",
      )
    }
  }
}
