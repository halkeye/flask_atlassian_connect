pipeline {
  agent {
    docker {
      image 'python:2.7'
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
        sh 'invoke docs'
      }
    }

    stage('Deploy Docs') {
      when { branch 'master' }
      environment { SURGE = credentials('halkeye-surge') }
      steps {
        sh 'SURGE_LOGIN=$SURGE_USR SURGE_TOKEN=$SURGE_PSW npx surge -p docs -d flask-atlassian-connect.surge.sh'
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
