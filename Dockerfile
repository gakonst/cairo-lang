FROM ciimage/python:3.7

RUN apt update
RUN apt install -y cmake libgmp3-dev g++ python3-pip python3.7-dev python3.7-venv npm

# Install solc and ganache
RUN curl https://binaries.soliditylang.org/linux-amd64/solc-linux-amd64-v0.6.12+commit.27d51765 -o /usr/local/bin/solc-0.6.12
RUN echo 'f6cb519b01dabc61cab4c184a3db11aa591d18151e362fcae850e42cffdfb09a /usr/local/bin/solc-0.6.12' | sha256sum --check
RUN chmod +x /usr/local/bin/solc-0.6.12
RUN npm install -g --unsafe-perm ganache-cli@6.12.2

COPY . /app/

# Build.
WORKDIR /app/
RUN ./build.sh

WORKDIR /app/build/Release
RUN make all -j8

# Run tests.
RUN ctest -V

WORKDIR /app/
RUN src/starkware/cairo/lang/package_test/run_test.sh

# Build the Visual Studio Code extension.
WORKDIR /app/src/starkware/cairo/lang/ide/vscode-cairo
RUN npm install -g vsce@1.87.1
RUN npm install
RUN vsce package

WORKDIR /app/
