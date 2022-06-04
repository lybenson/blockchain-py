# {
#     'index': 0,
#     'timestamp': '',
#     'transactions': [
#
#     ],
#     'proof': '',
#     'previous_hash': ''
# }
import json
from time import time
import hashlib
from urllib.parse import urlparse
from argparse import ArgumentParser
import requests
from flask import Flask, jsonify, request


class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []

        # 所有的节点信息
        self.nodes = set()

        # 创建创世区块
        self.new_block(proof=0, previous_hash=1)

    # 注册节点
    def register_node(self, address: str):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    # 解决不同节点的冲突（区块同步）
    def resolve_conflicts(self):
        neighbours = self.nodes

        # 自身节点的链的长度
        max_length = len(self.chain)
        new_chain = self.chain

        # 遍历所有的节点
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                response = response.json()
                length = response['length']

                # 所有的区块
                chain = response['chain']

                # 如果外部节点链的长度大于自身长度，且链有效
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

    # 验证链的有效性
    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        # 遍历每一个区块
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    # 创建区块
    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block),
        }

        self.current_transactions = []
        self.chain.append(block)

        return block

    # 创建交易记录
    def new_transactions(self, sender, recipient, amount):
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })

        return self.last_block['index'] + 1

    # 根据区块内容 生成hash
    @staticmethod
    def hash(block):
        block = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block).hexdigest()

    # 获取最后一个区块内容
    @property
    def last_block(self):
        return self.chain[-1]

    # 计算 proof
    def proof_of_work(self, last_proof: int) -> int:
        proof = 0
        # 每次将 proof + 1, 直到将 last_proof + proof 经过hash运算后前4位是 0000
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    # 验证proof: last_proof + proof 经过hash运算后前4位是 0000
    def valid_proof(self, last_proof: int, proof: int) -> bool:
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        return guess_hash[0:4] == '0000'


app = Flask(__name__)
blockChain = Blockchain()


@app.route('/index', methods=['GET'])
def index():
    return 'hello'


# 创建交易
@app.route('/transactions/new', methods=['POST'])
def new_transactions():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']

    if values is None:
        return 'missing values', 400

    if not all(k in values for k in required):
        return 'missing values', 400

    index = blockChain.new_transactions(values['sender'], values['recipient'], values['amount'])
    response = {
        'message': f'transactions will be added to block {index}'
    }
    return jsonify(response), 201


# 挖矿
@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockChain.last_block

    # 获取最新的区块的 proof
    last_proof = last_block['proof']

    # 根据 last_proof 生成新的 proof
    proof = blockChain.proof_of_work(last_proof)

    # 给自己添加奖励交易记录
    blockChain.new_transactions(sender=0, recipient='self address', amount=1)

    # 创建区块
    block = blockChain.new_block(proof, None)

    response = {
        'message': 'new Block',
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash']
    }

    return jsonify(response), 200


# 返回整个链
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockChain.chain,
        'length': len(blockChain.chain)
    }
    return jsonify(response), 200


# 注册节点 { nodes: ['http://127.0.0.1:5001'] }
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')

    if nodes is None:
        return 'Please supply a valid list of nodes', 400

    for node in nodes:
        blockChain.register_node(node)

    response = {
        'message': 'new node has been added',
        'total_nodes': list(blockChain.nodes)
    }
    return jsonify(response), 201


# 处理不同节点的冲突
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockChain.resolve_conflicts()
    if replaced:
        response = {
            'message': 'our chain was replaced',
            'new_chain': blockChain.chain
        }
    else:
        response = {
            'message': 'our chain was authoritative',
            'new_chain': blockChain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':

    # 通过终端传入端口号
    parse = ArgumentParser()

    parse.add_argument('-p', '--port', default=5000, type=int, help='port to listen to')
    args = parse.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)
