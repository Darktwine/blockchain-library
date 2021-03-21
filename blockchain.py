import hashlib
import json
from urllib.parse import urlparse
from uuid import uuid4
import requests
from flask import Flask, jsonify, request


class Blockchain:
    def __init__(self):
        self.chain = []
        self.request = []
        self.received_requests = []
        self.request_id = []
        self.transaction = []
        self.new_block(previous_hash='0')
        self.nodes = set()

    # add nodes
    def create_nodes(self, address):
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid')

    # proof of work testing (sends transactions to each node in network) except the node the book
    # was requested from
    def proof(self, book_key):
        network = self.nodes
        for node in network:
            if node != book_key:
                requests.post(f'http://{node}/add_transaction', data={
                    "sender_key": self.transaction[0]['sender_key'],
                    "receiver_key": self.transaction[0]['receiver_key'],
                    "book_key": self.transaction[0]['book_key']
                })
                response = requests.get(f'http://{node}/add_block')

    # consensus testing (adding longest chain)
    def consensus(self):
        self.proof(self.transaction[0]['book_key'])
        network = self.nodes
        check_chain = None
        length_chain = len(self.chain)
        for node in network:
            response = requests.get(f'http://{node}/get_chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > length_chain and self.validate_chain(chain):
                    length_chain = length
                    check_chain = chain
        if check_chain:
            self.chain = check_chain
            return True
        return False


    # transmitted request
    def get_new_requests(self, receiver_address):
        network = self.nodes
        for node in network:
            if node != receiver_address:
                response = requests.get(f'http://{node}/get_request')
                # print("Response is:", response)
                # print("Length is:", response.json()['length'])
                # print("Chain is:", response.json()['chain'])
                length = response.json()['length']
                chain = response.json()['chain']

        self.received_requests = chain

    def create_request_id(self, request_id):
        self.request_id.append({
            'request_id': request_id
        })

    def send_request(self, sender_address, receiver_address, request_message):
        # create a new request from the sender to the receiver
        network = self.nodes
        for node in network:
            if node == receiver_address:
                requests.post(f'http://{node}/set_request', json={
                    'sender_address': sender_address,
                    'receiver_address': receiver_address,
                    'request_message' : request_message
                })



    def set_request(self, sender_address, receiver_address, request_message):
        self.request.append({
            'sender_address': sender_address,
            'receiver_address': receiver_address,
            'request_message' : request_message
        })

 
    def send_request_id(self, sender_address, receiver_address):
        network = self.nodes
        for node in network:
            if node != receiver_address and node != sender_address:
                response = requests.get(f'http://{sender_address}/get_request_id')
                if response.status_code == 200:
                    requests.post(f'http://{node}/set_request_id', json={
                        'request_id': response.json()['request_id']
                    })


    def set_request_ids(self, request_id):
        self.request.append({
            'request_id': request_id
        })

    # creation of a new transaction, that would be a hash of the request id and book key
    # def new_transaction(self, sender_address, receiver_address, book_key):
    #     self.transaction.append({
    #         'proof': hashlib.sha256(self.request_id[0]['id'] + self.book_key[0]['key']).hexdigest()
    #     })
    #     return self.last_block['index'] + 1

    # creating a new block
    def new_block(self, previous_hash):
        block = {
            'index': len(self.chain) + 1,
            'transaction': self.transaction,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }
        self.transaction = []
        self.chain.append(block)
        return block

    # checks if chain is valid
    def validate_chain(self, chain):
        previous_block = chain[0]
        counter = 1
        while counter < len(chain):
            current_block = chain[counter]
            previous_hash = self.hash(previous_block)
            if current_block['previous_hash'] != previous_hash:
                return False
            previous_block = current_block
            counter = counter + 1
        return True

    # hash the block
    @staticmethod
    def hash(block):
        block_hash = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_hash).hexdigest()

    # gets last block from chain
    @property
    def last_block(self):
        return self.chain[-1]

    # gets last request
    @property
    def last_request(self):
        return self.request[-1]


app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
node_identifier = str(uuid4()).replace('-', '')
blockchain = Blockchain()

##### Route HTTP Methods #####

# create block
@app.route('/add_block', methods=['GET'])
def add_block():
    last_block = blockchain.last_block
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(previous_hash)
    response = {
        'message': "new block",
        'index': block['index'],
        'transaction': block['transaction'],
        'previous_hash': block['previous_hash']
    }
    return jsonify(response), 200


# Generate a request
@app.route('/add_request', methods=['POST'])
def add_request():
    # convert the POST info into JSON format, and save into requested_info
    request_info = request.get_json()

    # must have these keys for the request to be valid, generate an error if any are missing
    required = ['sender_address', 'receiver_address', 'request_message']
    if not all(keys in request_info for keys in required):
        return 'Missing keys for request', 400


    # Create and add request id to self
    request_id = uuid4()
    blockchain.create_request_id(request_id)

    # Send the information to the address of the receiver node
    blockchain.send_request(request_info['sender_address'], request_info['receiver_address'], request_info['request_message'])

    # Send request id to all the other nodes except the receiver of the request
    blockchain.send_request_id(request_info['sender_address'], request_info['receiver_address'])

    response = {'message': f"Request for {request_info['receiver_address']} and the request id has been created."}
    return jsonify(response), 201

@app.route('/set_request', methods=['POST'])
def set_request():
    # convert the POST info into JSON format, and save into requested_info
    request_info = request.get_json()

    # must have these keys for the request to be valid, generate an error if any are missing
    required = ['sender_address', 'receiver_address', 'request_message']
    if not all(keys in request_info for keys in required):
        return 'Missing keys for request', 400

    # Send the information to the address of the receiver node
    blockchain.set_request(request_info['sender_address'], request_info['receiver_address'], request_info['request_message'])

    response = {'message': f"The request has been sent for {request_info['receiver_address']}."}
    return jsonify(response), 201

@app.route('/set_request_id', methods=['POST'])
def set_request_id():
    # convert the POST info into JSON format, and save into requested_info
    request_info = request.get_json()
    required = ['request_id']
    if not all(keys in request_info for keys in required):
        return 'Missing keys for request', 400

    blockchain.set_request_ids(request_info['request_id'])
    response = {'message': "The request id has been sent to the other nodes."}
    return jsonify(response), 201

# create transaction
# @app.route('/add_transaction', methods=['POST'])
# def add_transaction():
#     values = request.get_json()
#     required = ['sender_key', 'receiver_key', 'book_key']
#     if not all(keys in values for keys in required):
#         return 'Missing keys', 400
#     # testing
#     #apple = nodes
#     #key = b'apple'
#     # encryptor = Salsa20.new(key)
#     index = blockchain.new_transaction((values['sender_key']),
#                                        (values['receiver_key']),
#                                        (values['book_key']))
#     response = {'message': f' New transaction for block {index} and transaction {len(blockchain.transaction)} '}
#     return jsonify(response), 201

# returns chain
@app.route('/get_chain', methods=['GET'])
def get_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200

# returns request
@app.route('/get_request', methods=['GET'])
def get_request():
    response = {
        'sender_address': blockchain.request[0]['sender_address'],
        'receiver_address': blockchain.request[0]['receiver_address'],
        'request_message': blockchain.request[0]['request_message']
    }
    return jsonify(response), 200

# returns request id
@app.route('/get_request_id', methods=['GET'])
def get_request_id():
    response = {
        'request_id': blockchain.request_id[0]['request_id']
    }
    return jsonify(response), 200

# add new nodes
@app.route('/new_nodes', methods=['POST'])
def new_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if nodes is None:
        return "Error", 400
    for node in nodes:
        blockchain.create_nodes(node)
    response = {
        'message': "Node created",
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201

# @app.route('/view_request', methods=['GET'])
# def view_request():
#     blockchain.get_new_requests()
#     response = {
#         'message': 'Book request message',
#         'chain': blockchain.received_requests,
#         'length': len(blockchain.received_requests)
#     }
#     return jsonify(response), 200

@app.route('/check_consensus', methods=['GET'])
def check_consensus():
    good = blockchain.consensus()
    if good:
        response = {
            'message': 'New chain',
            'chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Consensus failed',
            'chain': blockchain.chain
        }
    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen to')
    args = parser.parse_args()
    port = args.port
    app.run(host='127.0.0.1', port=port)