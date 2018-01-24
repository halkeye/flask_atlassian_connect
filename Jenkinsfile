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
        sh 'invokce docs'
      }
    }
  }
}
